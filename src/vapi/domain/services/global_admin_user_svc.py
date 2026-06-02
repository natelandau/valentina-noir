"""Global-admin user management service.

Performs user CRUD on behalf of a global admin. Authorization is handled by
global_admin_guard on the controller, so this service deliberately skips the
tenant role-assignment matrix (full superuser bypass). Only data-validity rules
are enforced. Queries are not filtered by is_archived, so archived users are
visible and restorable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from vapi.constants import UserRole
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.lib.exceptions import ConflictError, NotFoundError, ValidationError
from vapi.lib.patch import apply_patch

if TYPE_CHECKING:
    from vapi.domain.controllers.global_admin.dto import AdminUserCreate, AdminUserPatch


class GlobalAdminUserService:
    """User CRUD for the global admin domain (no role matrix)."""

    async def create_user(self, data: AdminUserCreate) -> User:
        """Create a user in the company named by ``data.company_id``.

        The role matrix does not apply. UNAPPROVED and DEACTIVATED are not valid
        initial roles (use the register/approve flow for UNAPPROVED).

        Args:
            data: The admin user creation payload, including the target company_id.

        Returns:
            The created user with campaign_experiences prefetched.

        Raises:
            NotFoundError: If the target company does not exist or is archived.
            ValidationError: If the role is invalid or is UNAPPROVED/DEACTIVATED.
        """
        company = await Company.filter(id=data.company_id, is_archived=False).first()
        if not company:
            raise NotFoundError(detail="Company not found")

        try:
            new_role = UserRole(data.role)
        except ValueError as e:
            raise ValidationError(detail=f"Invalid role: {data.role}") from e

        if new_role in {UserRole.UNAPPROVED, UserRole.DEACTIVATED}:
            raise ValidationError(
                detail=f"Cannot create a user with initial role {new_role.value}",
            )

        user = await User.create(
            name_first=data.name_first,
            name_last=data.name_last,
            username=data.username,
            email=data.email,
            role=new_role,
            company=company,
            discord_profile=data.discord_profile,
            google_profile=data.google_profile,
            github_profile=data.github_profile,
        )
        await user.fetch_related("campaign_experiences")
        return user

    async def update_user(
        self, user: User, data: AdminUserPatch
    ) -> tuple[User, dict[str, dict[str, object]]]:
        """Update any field with no role-matrix restrictions.

        ``role`` is handled explicitly (not via apply_patch) so it is stored as a
        UserRole enum rather than a bare string -- UserResponse.from_model reads
        ``role.value``. Archiving via this patch (is_archived false -> true)
        cascades to owned data exactly like delete_user; setting is_archived to
        false reverses that cascade, restoring the user and the data archived
        with them as a unit. Restoring is refused while the user's company is
        archived (the company must be restored first).

        Args:
            user: The user to update.
            data: The patch payload; only non-UNSET fields are applied.

        Returns:
            The saved user (campaign_experiences prefetched) and a diff dict of
            changed fields for audit logging.

        Raises:
            ValidationError: If the patch sets an invalid role.
            ConflictError: If restoring the user while their company is archived.
        """
        was_archived = user.is_archived
        # Capture before apply_patch/save clears it, so restore can reverse the batch.
        restore_batch_id = user.archive_batch_id if was_archived else None

        changes = apply_patch(user, data, exclude=frozenset({"role"}))

        if not isinstance(data.role, msgspec.UnsetType):
            try:
                new_role = UserRole(data.role)
            except ValueError as e:
                raise ValidationError(detail=f"Invalid role: {data.role}") from e
            if user.role != new_role:
                changes["role"] = {"old": user.role, "new": new_role}
                user.role = new_role

        going_to_restore = was_archived and not user.is_archived
        if going_to_restore:
            # A flat batch means restoring a user archived as part of a company
            # archive would resurrect the whole tenant; refuse and require the
            # company be restored first.
            await user.fetch_related("company")
            if user.company.is_archived:
                raise ConflictError(
                    detail="Cannot restore a user while their company is archived; "
                    "restore the company first."
                )

        await user.save()

        from vapi.domain.handlers import cascade_archive_user, restore_archive_batch

        if not was_archived and user.is_archived:
            # Archiving via patch cascades to owned data under the user's batch,
            # identically to delete_user.
            await cascade_archive_user(user)
        elif going_to_restore and restore_batch_id is not None:
            # Restoring reverses the original archive action as a unit. The user
            # row itself was already cleared by save(); this restores the rest.
            await restore_archive_batch(batch_id=restore_batch_id)

        await user.fetch_related("campaign_experiences")
        return user, changes

    async def delete_user(self, user: User) -> None:
        """Soft-delete a user and cascade archival to their owned data.

        Mirrors the tenant delete path: the user record is archived and the
        cascade archives their quickrolls, assets, and played characters. The
        last-admin guard is intentionally NOT applied here -- a global admin may
        remove any user. Restorable via update with is_archived=false, which
        reverses the cascade.

        Args:
            user: The user to soft-delete.
        """
        from vapi.domain.handlers import cascade_archive_user

        user.is_archived = True
        await user.save()
        await cascade_archive_user(user)
