"""User service."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import msgspec
from tortoise.expressions import F

from vapi.constants import COOL_POINT_VALUE, PermissionsGrantXP, UserRole
from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.user import CampaignExperience, User
from vapi.domain.utils import validate_trait_ids_from_mixed_sources
from vapi.lib.exceptions import (
    ConflictError,
    NotEnoughXPError,
    PermissionDeniedError,
    ValidationError,
)

from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from uuid import UUID

    from vapi.db.sql_models.company import Company
    from vapi.domain.controllers.user.dto import UserCreate, UserPatch, UserRegister


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
        - UNAPPROVED is never a valid assignment target (use approve/deny/register flow).
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
                company_id=target_user.company_id,  # type: ignore[attr-defined]
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

    async def create_user(self, company: Company, data: UserCreate) -> User:
        """Create a user in a company.

        The initial role is validated through the role-assignment matrix.
        Creating a user with role UNAPPROVED (use register_user) or DEACTIVATED
        (not a creation path) is forbidden.

        Args:
            company: The company to add the user to.
            data: The user creation data.

        Returns:
            The created user with campaign_experiences prefetched.
        """
        requesting_user = await self._assert_requester_active(data.requesting_user_id)
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
            discord_profile=data.discord_profile,
            google_profile=data.google_profile,
            github_profile=data.github_profile,
        )
        await user.fetch_related("campaign_experiences")
        return user

    async def register_user(self, company: Company, data: UserRegister) -> User:
        """Register a new user with the UNAPPROVED role.

        Designed for SSO onboarding where no existing Valentina user is making the
        request. Developer API key auth is sufficient -- no requesting_user_id needed.

        Args:
            company: The company to register the user in.
            data: The registration data.

        Returns:
            The created user with campaign_experiences prefetched.
        """
        user = await User.create(
            name_first=data.name_first,
            name_last=data.name_last,
            username=data.username,
            email=data.email,
            role=UserRole.UNAPPROVED,
            company=company,
            discord_profile=data.discord_profile,
            google_profile=data.google_profile,
            github_profile=data.github_profile,
        )
        await user.fetch_related("campaign_experiences")
        return user

    async def merge_users(
        self,
        *,
        primary_user_id: UUID,
        secondary_user_id: UUID,
        company: Company,
        requesting_user_id: UUID,
    ) -> User:
        """Merge an UNAPPROVED secondary user into an existing primary user.

        Copy OAuth profile fields from secondary to primary (only filling empty fields),
        then archive the secondary user.

        Args:
            primary_user_id: The ID of the user account that survives.
            secondary_user_id: The ID of the UNAPPROVED user whose profile info is absorbed.
            company: The company both users belong to.
            requesting_user_id: The admin performing the merge.

        Raises:
            ValidationError: If the secondary user is not UNAPPROVED or users are the same.
            PermissionDeniedError: If the requesting user is not an admin.
        """
        from vapi.domain import deps

        await self._assert_requester_active(requesting_user_id)
        await self.validate_user_can_manage_user(requesting_user_id=requesting_user_id)

        if primary_user_id == secondary_user_id:
            raise ValidationError(detail="Cannot merge a user with themselves")

        primary_user, secondary_user = await asyncio.gather(
            deps.provide_user_by_id_and_company(user_id=primary_user_id, company=company),
            deps.provide_user_by_id_and_company(user_id=secondary_user_id, company=company),
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
        for attr in ("google_profile", "github_profile", "discord_profile"):
            primary_profile = getattr(primary, attr) or {}
            secondary_profile = getattr(secondary, attr) or {}
            changed = False

            for key, secondary_value in secondary_profile.items():
                if secondary_value is not None and primary_profile.get(key) is None:
                    primary_profile[key] = secondary_value
                    changed = True

            if changed:
                setattr(primary, attr, primary_profile)

    async def update_user(self, user: User, data: UserPatch) -> User:
        """Update a user with partial data.

        Role changes always route through the role-assignment matrix — even for
        self-edits — which closes the prior self-PATCH escalation path. Non-role
        fields continue to allow self-or-admin edits.

        Args:
            user: The user to update.
            data: The patch data with UNSET defaults for unsent fields.

        Returns:
            The updated user with campaign_experiences prefetched.
        """
        requesting_user = await self._assert_requester_active(data.requesting_user_id)

        if not isinstance(data.role, msgspec.UnsetType):
            new_role = UserRole(data.role)
            await self._validate_role_assignment(
                requesting_user=requesting_user,
                target_user=user,
                new_role=new_role,
            )
            if user.role == UserRole.ADMIN and new_role != UserRole.ADMIN:
                await self._assert_not_last_admin(user)
            user.role = new_role

        await self.validate_user_can_manage_user(
            requesting_user_id=data.requesting_user_id,
            user_to_manage_id=user.id,
        )

        if not isinstance(data.name_first, msgspec.UnsetType):
            user.name_first = data.name_first
        if not isinstance(data.name_last, msgspec.UnsetType):
            user.name_last = data.name_last
        if not isinstance(data.username, msgspec.UnsetType):
            user.username = data.username
        if not isinstance(data.email, msgspec.UnsetType):
            user.email = data.email
        if not isinstance(data.discord_profile, msgspec.UnsetType):
            user.discord_profile = data.discord_profile
        if not isinstance(data.google_profile, msgspec.UnsetType):
            user.google_profile = data.google_profile
        if not isinstance(data.github_profile, msgspec.UnsetType):
            user.github_profile = data.github_profile

        await user.save()
        await user.fetch_related("campaign_experiences")
        return user

    async def remove_and_archive_user(self, *, user: User, company: Company) -> None:  # noqa: ARG002
        """Archive a user and cascade archival to related data.

        Args:
            user: The user to archive.
            company: The company the user belongs to (unused - FK handles relationship).
        """
        from vapi.domain.handlers.archive_handlers import archive_user_cascade

        await self._assert_not_last_admin(user)

        user.is_archived = True
        await user.save()
        await archive_user_cascade(user.id)

    async def approve_user(
        self,
        *,
        user: User,
        role: UserRole,
        requesting_user_id: UUID,
    ) -> User:
        """Approve an unapproved user and assign a role.

        Args:
            user: The unapproved user to approve.
            role: The role to assign.
            requesting_user_id: The ID of the admin performing the action.

        Raises:
            ValidationError: If the user is not UNAPPROVED or the role is UNAPPROVED/DEACTIVATED.
            PermissionDeniedError: If the requester is not authorized for the assignment.
        """
        requesting_user = await self._assert_requester_active(requesting_user_id)
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
        requesting_user_id: UUID,
    ) -> None:
        """Deny an unapproved user and archive them.

        Args:
            user: The unapproved user to deny.
            company: The company the user belongs to.
            requesting_user_id: The ID of the admin performing the action.

        Raises:
            ValidationError: If the user is not UNAPPROVED.
            PermissionDeniedError: If the requesting user is not an admin.
        """
        await self._assert_requester_active(requesting_user_id)
        await self.validate_user_can_manage_user(requesting_user_id=requesting_user_id)

        if user.role != UserRole.UNAPPROVED:
            raise ValidationError(detail="User is not in UNAPPROVED status")

        await self.remove_and_archive_user(user=user, company=company)


class UserXPService:
    """XP and cool point management service.

    Handles all CampaignExperience CRUD and XP/CP math.
    """

    async def get_or_create_campaign_experience(
        self,
        user_id: UUID,
        campaign_id: UUID,
    ) -> CampaignExperience:
        """Get or create a campaign experience record for a user.

        Args:
            user_id: The user's UUID.
            campaign_id: The campaign's UUID.

        Returns:
            The existing or newly created CampaignExperience.
        """
        # Normalize to stdlib UUID so Tortoise's get_or_create handles both
        # uuid_utils.UUID and stdlib UUID transparently
        experience, _ = await CampaignExperience.get_or_create(
            user_id=uuid.UUID(str(user_id)),
            campaign_id=uuid.UUID(str(campaign_id)),
        )
        return experience

    async def add_xp(
        self,
        user_id: UUID,
        campaign_id: UUID,
        amount: int,
        *,
        update_total: bool = True,
    ) -> CampaignExperience:
        """Add XP to a campaign experience.

        Args:
            user_id: The user's UUID.
            campaign_id: The campaign's UUID.
            amount: The amount of XP to add.
            update_total: Whether to update xp_total and lifetime_xp.

        Returns:
            The updated CampaignExperience.
        """
        experience = await self.get_or_create_campaign_experience(user_id, campaign_id)
        experience.xp_current += amount

        if update_total:
            experience.xp_total += amount
            await User.filter(id=user_id).update(lifetime_xp=F("lifetime_xp") + amount)

        await experience.save()
        return experience

    async def spend_xp(
        self,
        user_id: UUID,
        campaign_id: UUID,
        amount: int,
    ) -> CampaignExperience:
        """Spend XP from a campaign experience.

        Args:
            user_id: The user's UUID.
            campaign_id: The campaign's UUID.
            amount: The amount of XP to spend.

        Raises:
            NotEnoughXPError: If the user does not have enough XP.
        """
        experience = await self.get_or_create_campaign_experience(user_id, campaign_id)

        if experience.xp_current < amount:
            raise NotEnoughXPError

        experience.xp_current -= amount
        await experience.save()
        return experience

    async def add_cp(
        self,
        user_id: UUID,
        campaign_id: UUID,
        amount: int,
    ) -> CampaignExperience:
        """Add cool points to a campaign experience, converting to XP.

        Each cool point is worth COOL_POINT_VALUE XP.

        Args:
            user_id: The user's UUID.
            campaign_id: The campaign's UUID.
            amount: The number of cool points to add.

        Returns:
            The updated CampaignExperience.
        """
        xp_amount = amount * COOL_POINT_VALUE
        experience = await self.get_or_create_campaign_experience(user_id, campaign_id)

        experience.cool_points += amount
        experience.xp_current += xp_amount
        experience.xp_total += xp_amount
        await experience.save()

        await User.filter(id=user_id).update(
            lifetime_xp=F("lifetime_xp") + xp_amount,
            lifetime_cool_points=F("lifetime_cool_points") + amount,
        )

        return experience

    async def _validate_user_can_grant_xp(
        self,
        company: Company,
        requesting_user_id: UUID,
        target_user_id: UUID,
    ) -> None:
        """Validate if the user can grant XP.

        Raises:
            PermissionDeniedError: If the user is not authorized to grant XP.
        """
        requesting_user = await GetModelByIdValidationService().get_user_by_id(requesting_user_id)
        if (
            company.settings.permission_grant_xp == PermissionsGrantXP.UNRESTRICTED
            or requesting_user.role
            in [
                UserRole.STORYTELLER,
                UserRole.ADMIN,
            ]
        ):
            return

        if (
            company.settings.permission_grant_xp == PermissionsGrantXP.PLAYER
            and requesting_user.id == target_user_id
        ):
            return

        raise PermissionDeniedError(
            detail="User not authorized to grant or remove XP for this user"
        )

    async def add_xp_to_campaign_experience(
        self,
        *,
        company: Company,
        requesting_user_id: UUID,
        target_user: User,
        campaign_id: UUID,
        amount: int,
    ) -> CampaignExperience:
        """Add XP to a campaign experience with permission validation."""
        await UserService()._assert_requester_active(requesting_user_id)  # noqa: SLF001
        await self._validate_user_can_grant_xp(
            company=company,
            requesting_user_id=requesting_user_id,
            target_user_id=target_user.id,
        )
        return await self.add_xp(target_user.id, campaign_id, amount)

    async def remove_xp_from_campaign_experience(
        self,
        *,
        company: Company,
        requesting_user_id: UUID,
        target_user: User,
        campaign_id: UUID,
        amount: int,
    ) -> CampaignExperience:
        """Remove XP from a campaign experience with permission validation."""
        await UserService()._assert_requester_active(requesting_user_id)  # noqa: SLF001
        await self._validate_user_can_grant_xp(
            company=company,
            requesting_user_id=requesting_user_id,
            target_user_id=target_user.id,
        )
        return await self.spend_xp(target_user.id, campaign_id, amount)

    async def add_cp_to_campaign_experience(
        self,
        *,
        company: Company,
        requesting_user_id: UUID,
        target_user: User,
        campaign_id: UUID,
        amount: int,
    ) -> CampaignExperience:
        """Add cool points to a campaign experience with permission validation."""
        await UserService()._assert_requester_active(requesting_user_id)  # noqa: SLF001
        await self._validate_user_can_grant_xp(
            company=company,
            requesting_user_id=requesting_user_id,
            target_user_id=target_user.id,
        )
        return await self.add_cp(target_user.id, campaign_id, amount)


class UserQuickRollService:
    """Quick roll service."""

    async def validate_quickroll_traits(self, trait_ids: list[UUID]) -> list[Trait]:
        """Validate trait IDs and return the Trait objects for M2M assignment.

        Args:
            trait_ids: The list of trait UUIDs to validate.

        Returns:
            The list of validated Trait objects.

        Raises:
            ValidationError: If no traits remain after validation or any ID is invalid.
        """
        validated_ids = await validate_trait_ids_from_mixed_sources(trait_ids)

        if not validated_ids:
            raise ValidationError(
                detail="Quick roll must have at least one trait",
                invalid_parameters=[
                    {
                        "field": "trait_ids",
                        "message": "Quick roll must have at least one trait",
                    },
                ],
            )

        return await Trait.filter(id__in=validated_ids)
