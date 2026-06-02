"""Global-admin user management service.

Performs user CRUD on behalf of a global admin. Authorization is handled by
global_admin_guard on the controller, so this service deliberately skips the
tenant role-assignment matrix (full superuser bypass). Only data-validity rules
are enforced. Queries are not filtered by is_archived, so archived users are
visible and restorable.
"""

import msgspec

from vapi.constants import UserRole
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.lib.exceptions import NotFoundError, ValidationError
from vapi.lib.patch import apply_patch

from .dto import AdminUserCreate, AdminUserPatch


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
        ``role.value``. Setting ``is_archived`` to false restores the user.

        Args:
            user: The user to update.
            data: The patch payload; only non-UNSET fields are applied.

        Returns:
            The saved user (campaign_experiences prefetched) and a diff dict of
            changed fields for audit logging.

        Raises:
            ValidationError: If the patch sets an invalid role.
        """
        changes = apply_patch(user, data, exclude=frozenset({"role"}))

        if not isinstance(data.role, msgspec.UnsetType):
            try:
                new_role = UserRole(data.role)
            except ValueError as e:
                raise ValidationError(detail=f"Invalid role: {data.role}") from e
            if user.role != new_role:
                changes["role"] = {"old": user.role, "new": new_role}
                user.role = new_role

        await user.save()
        await user.fetch_related("campaign_experiences")
        return user, changes

    async def delete_user(self, user: User) -> None:
        """Soft-delete a user and cascade archival to their owned data.

        Mirrors the tenant delete path: the user record is archived and the
        cascade archives their quickrolls, assets, and played characters. The
        last-admin guard is intentionally NOT applied here -- a global admin may
        remove any user. Restorable via update with is_archived=false (the
        cascade is not reversed on restore).

        Args:
            user: The user to soft-delete.
        """
        from vapi.domain.handlers.archive_handlers import archive_user_cascade

        user.is_archived = True
        await user.save()
        await archive_user_cascade(user.id)
