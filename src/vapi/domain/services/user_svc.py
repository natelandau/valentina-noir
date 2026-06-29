"""User service."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import msgspec
from tortoise.expressions import Q
from tortoise.functions import Count
from tortoise.transactions import in_transaction

from vapi.constants import (
    PROVIDER_PROFILE_FIELDS,
    UserRole,
)
from vapi.db.sql_models.user import User
from vapi.lib.exceptions import (
    ConflictError,
    PermissionDeniedError,
    ValidationError,
)
from vapi.lib.patch import apply_patch

from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from uuid import UUID

    from tortoise.queryset import QuerySet

    from vapi.db.sql_models.company import Company
    from vapi.domain.controllers.user.dto import UserCreate, UserPatch


def annotate_user_counts(qs: QuerySet[User]) -> QuerySet[User]:
    """Annotate a User queryset with active child-resource counts for responses.

    played_characters needs no type filter: NPC and storyteller characters belong to
    the campaign and never have a player, so played_characters is player-only.
    """
    return qs.annotate(
        num_quickrolls=Count(
            "quick_rolls", _filter=Q(quick_rolls__is_archived=False), distinct=True
        ),
        num_notes=Count("notes", _filter=Q(notes__is_archived=False), distinct=True),
        num_assets=Count("owned_assets", _filter=Q(owned_assets__is_archived=False), distinct=True),
        num_characters=Count(
            "played_characters", _filter=Q(played_characters__is_archived=False), distinct=True
        ),
    )


class UserService:
    """User service."""

    async def _assert_requester_active(self, requesting_user_id: UUID) -> User:
        """Reject requesters that cannot act on any endpoint and return the fetched user.

        Called from every user-surface mutation path because route guards
        cannot inspect body-supplied requesting_user_id. Returns the loaded User
        so callers can reuse it (e.g. for role-matrix checks) without a second fetch.

        Raises:
            PermissionDeniedError: If the requesting user is UNAPPROVED or DEACTIVATED.
        """
        requesting_user = await GetModelByIdValidationService().get_user_by_id(requesting_user_id)
        if requesting_user.role == UserRole.UNAPPROVED:
            raise PermissionDeniedError(detail="User has not been approved yet")
        if requesting_user.role == UserRole.DEACTIVATED:
            raise PermissionDeniedError(detail="User account is deactivated")
        return requesting_user

    async def _validate_role_assignment(
        self,
        *,
        requesting_user: User,
        target_user: User,
        new_role: UserRole,
    ) -> None:
        """Enforce the role-assignment authorization matrix.

        Rules:
        - UNAPPROVED is never a valid assignment target (use the approve/deny flow).
        - Only ADMIN may modify an ADMIN target's role.
        - Only ADMIN may assign or remove DEACTIVATED.
        - STORYTELLER may only assign STORYTELLER or PLAYER to non-admin targets.
        - PLAYER / UNAPPROVED / DEACTIVATED requesters may not change any role.

        Does not check the last-admin invariant — callers layer that check on top.

        Raises:
            PermissionDeniedError: If the requester is not authorized for this transition.
            ValidationError: If the target role is UNAPPROVED.
        """
        if new_role == UserRole.UNAPPROVED:
            raise ValidationError(detail="Cannot assign UNAPPROVED role")

        requester_role = requesting_user.role

        if requester_role not in {UserRole.ADMIN, UserRole.STORYTELLER}:
            raise PermissionDeniedError(
                detail="Requesting user is not authorized to change user roles",
            )

        if (
            UserRole.DEACTIVATED in {new_role, target_user.role}
            and requester_role != UserRole.ADMIN
        ):
            raise PermissionDeniedError(
                detail="Only admins may deactivate or reactivate a user",
            )

        if target_user.role == UserRole.ADMIN and requester_role != UserRole.ADMIN:
            raise PermissionDeniedError(
                detail="Only admins may change an admin user's role",
            )

        if requester_role == UserRole.STORYTELLER and new_role not in {
            UserRole.STORYTELLER,
            UserRole.PLAYER,
        }:
            raise PermissionDeniedError(
                detail="Storytellers may only assign STORYTELLER or PLAYER roles",
            )

    async def _assert_not_last_admin(self, target_user: User) -> None:
        """Block mutations that would leave a company with zero active admins.

        No-op if the target is not currently ADMIN.

        Raises:
            ConflictError: If removing this user as admin would leave the company
                with zero non-archived admins. Rendered as HTTP 409.
        """
        if target_user.role != UserRole.ADMIN:
            return

        remaining = (
            await User.filter(
                company_id=target_user.company_id,  # ty:ignore[unresolved-attribute]
                role=UserRole.ADMIN,
                is_archived=False,
            )
            .exclude(id=target_user.id)
            .count()
        )

        if remaining == 0:
            raise ConflictError(
                detail="Cannot remove the last admin from the company",
            )

    async def validate_user_can_manage_user(
        self,
        requesting_user_id: UUID,
        user_to_manage_id: UUID | None = None,
    ) -> None:
        """Validate if the requesting user has permission to manage another user.

        Args:
            requesting_user_id: The ID of the user requesting to manage the user.
            user_to_manage_id: The ID of the user to manage.

        Raises:
            ValidationError: If the requesting user is not found.
            PermissionDeniedError: If the requesting user is not authorized.
        """
        if user_to_manage_id and requesting_user_id == user_to_manage_id:
            return

        requesting_user = await GetModelByIdValidationService().get_user_by_id(requesting_user_id)
        if requesting_user.role != UserRole.ADMIN:
            raise PermissionDeniedError(
                detail="Requesting user is not authorized to manage this user",
            )

    async def create_user(self, company: Company, data: UserCreate, acting_user_id: UUID) -> User:
        """Create a user in a company.

        The initial role is validated through the role-assignment matrix.
        Creating a user with role UNAPPROVED (use the verified identify endpoint)
        or DEACTIVATED (not a creation path) is forbidden.

        Args:
            company: The company to add the user to.
            data: The user creation data.
            acting_user_id: The ID of the user performing the action.

        Returns:
            The created user with campaign_experiences prefetched.
        """
        requesting_user = await self._assert_requester_active(acting_user_id)
        new_role = UserRole(data.role)

        if new_role in {UserRole.UNAPPROVED, UserRole.DEACTIVATED}:
            raise ValidationError(detail=f"Cannot create a user with initial role {new_role.value}")

        # Synthetic unsaved target with role=PLAYER so the matrix evaluates
        # requester-vs-new_role without needing a real existing user.
        synthetic_target = User(role=UserRole.PLAYER, company_id=company.id)
        await self._validate_role_assignment(
            requesting_user=requesting_user,
            target_user=synthetic_target,
            new_role=new_role,
        )

        user = await User.create(
            name_first=data.name_first,
            name_last=data.name_last,
            username=data.username,
            email=data.email,
            role=new_role,
            company=company,
        )
        await user.fetch_related("campaign_experiences")
        return user

    async def merge_users(
        self,
        *,
        primary_user_id: UUID,
        secondary_user_id: UUID,
        company: Company,
        acting_user_id: UUID,
    ) -> User:
        """Merge an UNAPPROVED secondary user into an existing primary user.

        Copy OAuth profile fields from secondary to primary (only filling empty fields),
        then archive the secondary user.

        Args:
            primary_user_id: The ID of the user account that survives.
            secondary_user_id: The ID of the UNAPPROVED user whose profile info is absorbed.
            company: The company both users belong to.
            acting_user_id: The admin performing the merge.

        Raises:
            ValidationError: If the secondary user is not UNAPPROVED or users are the same.
            PermissionDeniedError: If the requesting user is not an admin.
        """
        from vapi.domain import deps

        await self._assert_requester_active(acting_user_id)
        await self.validate_user_can_manage_user(requesting_user_id=acting_user_id)

        if primary_user_id == secondary_user_id:
            raise ValidationError(detail="Cannot merge a user with themselves")

        primary_user, secondary_user = await asyncio.gather(
            deps.provide_target_user(user_id=primary_user_id, company=company),
            deps.provide_target_user(user_id=secondary_user_id, company=company),
        )

        if secondary_user.role != UserRole.UNAPPROVED:
            raise ValidationError(detail="Secondary user must have UNAPPROVED role")

        self._absorb_profiles(primary=primary_user, secondary=secondary_user)
        await primary_user.save()

        await self.remove_and_archive_user(user=secondary_user, company=company)

        await primary_user.fetch_related("campaign_experiences")
        return primary_user

    @staticmethod
    def _absorb_profiles(*, primary: User, secondary: User) -> None:
        """Copy non-empty profile fields from secondary to primary where primary is empty.

        Operates on JSON dict fields. After merging, explicitly reassigns the profile
        field on the model to ensure Tortoise detects the change for save.

        Args:
            primary: The target user whose empty profile fields get filled.
            secondary: The source user whose profile fields are copied.
        """
        for attr in PROVIDER_PROFILE_FIELDS.values():
            primary_profile = getattr(primary, attr) or {}
            secondary_profile = getattr(secondary, attr) or {}
            changed = False

            for key, secondary_value in secondary_profile.items():
                if secondary_value is not None and primary_profile.get(key) is None:
                    primary_profile[key] = secondary_value
                    changed = True

            if changed:
                setattr(primary, attr, primary_profile)

    async def update_user(
        self, user: User, data: UserPatch, acting_user_id: UUID
    ) -> tuple[User, dict[str, dict[str, object]]]:
        """Update a user with partial data and return a diff of what changed.

        Role changes always route through the role-assignment matrix — even for
        self-edits — which closes the prior self-PATCH escalation path. Non-role
        fields continue to allow self-or-admin edits.

        Args:
            user: The user to update.
            data: The patch data with UNSET defaults for unsent fields.
            acting_user_id: The ID of the user performing the action.

        Returns:
            Tuple of (updated user with campaign_experiences prefetched, changes dict).
        """
        requesting_user = await self._assert_requester_active(acting_user_id)

        role_change: dict[str, dict[str, object]] = {}
        if not isinstance(data.role, msgspec.UnsetType):
            old_role = user.role
            new_role = UserRole(data.role)
            await self._validate_role_assignment(
                requesting_user=requesting_user,
                target_user=user,
                new_role=new_role,
            )
            if user.role == UserRole.ADMIN and new_role != UserRole.ADMIN:
                await self._assert_not_last_admin(user)
            if old_role != new_role:
                role_change["role"] = {"old": old_role, "new": new_role}
            user.role = new_role

        await self.validate_user_can_manage_user(
            requesting_user_id=acting_user_id,
            user_to_manage_id=user.id,
        )

        changes = apply_patch(user, data, exclude=frozenset({"role"}))
        changes.update(role_change)

        await user.save()
        await user.fetch_related("campaign_experiences")
        return user, changes

    async def remove_and_archive_user(self, *, user: User, company: Company) -> None:  # noqa: ARG002
        """Archive a user and cascade archival to related data.

        Args:
            user: The user to archive.
            company: The company the user belongs to (unused - FK handles relationship).
        """
        # Local import: user_svc is pulled into the services import graph (via
        # character_trait_svc) before CharacterTraitService is bound, so a
        # top-level handlers import would cycle.
        from vapi.domain.handlers import cascade_archive_user

        await self._assert_not_last_admin(user)

        async with in_transaction():
            user.is_archived = True
            await user.save()
            await cascade_archive_user(user)

    async def approve_user(
        self,
        *,
        user: User,
        role: UserRole,
        acting_user_id: UUID,
    ) -> User:
        """Approve an unapproved user and assign a role.

        Args:
            user: The unapproved user to approve.
            role: The role to assign.
            acting_user_id: The ID of the admin performing the action.

        Raises:
            ValidationError: If the user is not UNAPPROVED or the role is UNAPPROVED/DEACTIVATED.
            PermissionDeniedError: If the requester is not authorized for the assignment.
        """
        requesting_user = await self._assert_requester_active(acting_user_id)
        if requesting_user.role != UserRole.ADMIN:
            raise PermissionDeniedError(
                detail="Requesting user is not authorized to manage this user",
            )

        if user.role != UserRole.UNAPPROVED:
            raise ValidationError(detail="User is not in UNAPPROVED status")

        if role in {UserRole.UNAPPROVED, UserRole.DEACTIVATED}:
            raise ValidationError(detail=f"Cannot assign {role.value} role via approval")

        await self._validate_role_assignment(
            requesting_user=requesting_user,
            target_user=user,
            new_role=role,
        )

        user.role = role
        await user.save()
        return user

    async def deny_user(
        self,
        *,
        user: User,
        company: Company,
        acting_user_id: UUID,
    ) -> None:
        """Deny an unapproved user and archive them.

        Args:
            user: The unapproved user to deny.
            company: The company the user belongs to.
            acting_user_id: The ID of the admin performing the action.

        Raises:
            ValidationError: If the user is not UNAPPROVED.
            PermissionDeniedError: If the requesting user is not an admin.
        """
        await self._assert_requester_active(acting_user_id)
        await self.validate_user_can_manage_user(requesting_user_id=acting_user_id)

        if user.role != UserRole.UNAPPROVED:
            raise ValidationError(detail="User is not in UNAPPROVED status")

        await self.remove_and_archive_user(user=user, company=company)
