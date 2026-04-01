"""User service."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import msgspec
from tortoise.expressions import F

from vapi.constants import COOL_POINT_VALUE, PermissionsGrantXP, UserRole
from vapi.db.models import QuickRoll
from vapi.db.sql_models.user import CampaignExperience, User
from vapi.domain.utils import validate_trait_ids_from_mixed_sources
from vapi.lib.exceptions import NotEnoughXPError, PermissionDeniedError, ValidationError

from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from uuid import UUID

    from vapi.db.sql_models.company import Company
    from vapi.domain.controllers.user.dto import UserCreate, UserPatch, UserRegister


class UserService:
    """User service."""

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

        Args:
            company: The company to add the user to.
            data: The user creation data.

        Returns:
            The created user with campaign_experiences prefetched.
        """
        await self.validate_user_can_manage_user(
            requesting_user_id=data.requesting_user_id,
        )

        user = await User.create(
            name_first=data.name_first,
            name_last=data.name_last,
            username=data.username,
            email=data.email,
            role=UserRole(data.role),
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
        from vapi.domain import pg_deps

        await self.validate_user_can_manage_user(requesting_user_id=requesting_user_id)

        if primary_user_id == secondary_user_id:
            raise ValidationError(detail="Cannot merge a user with themselves")

        primary_user, secondary_user = await asyncio.gather(
            pg_deps.provide_user_by_id_and_company(user_id=primary_user_id, company=company),
            pg_deps.provide_user_by_id_and_company(user_id=secondary_user_id, company=company),
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

        Args:
            user: The user to update.
            data: The patch data with UNSET defaults for unsent fields.

        Returns:
            The updated user with campaign_experiences prefetched.
        """
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
        if not isinstance(data.role, msgspec.UnsetType):
            user.role = UserRole(data.role)
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
        """Archive a user and cascade archival to related Beanie data.

        Args:
            user: The user to archive.
            company: The company the user belongs to (unused — FK handles relationship).
        """
        from vapi.domain.handlers.archive_handlers import archive_user_cascade

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
            ValidationError: If the user is not UNAPPROVED or the role is UNAPPROVED.
            PermissionDeniedError: If the requesting user is not an admin.
        """
        await self.validate_user_can_manage_user(requesting_user_id=requesting_user_id)

        if user.role != UserRole.UNAPPROVED:
            raise ValidationError(detail="User is not in UNAPPROVED status")

        if role == UserRole.UNAPPROVED:
            raise ValidationError(detail="Cannot assign UNAPPROVED role")

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
        await self.validate_user_can_manage_user(requesting_user_id=requesting_user_id)

        if user.role != UserRole.UNAPPROVED:
            raise ValidationError(detail="User is not in UNAPPROVED status")

        await self.remove_and_archive_user(user=user, company=company)


class UserXPService:
    """XP and cool point management service.

    Handles all CampaignExperience CRUD and XP/CP math that previously lived
    as methods on the Beanie User model.
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
        experience, _ = await CampaignExperience.get_or_create(
            user_id=user_id,
            campaign_id=campaign_id,
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
        await self._validate_user_can_grant_xp(
            company=company,
            requesting_user_id=requesting_user_id,
            target_user_id=target_user.id,
        )
        return await self.add_cp(target_user.id, campaign_id, amount)


class UserQuickRollService:
    """Quick roll service.

    Stays on Beanie — QuickRoll migrates in a later session.
    """

    async def validate_quickroll(self, quickroll: QuickRoll) -> QuickRoll:
        """Validate a quick roll's trait IDs and name uniqueness.

        Args:
            quickroll: The quick roll to validate.

        Returns:
            The validated quick roll with resolved trait IDs.

        Raises:
            ValidationError: If no traits remain after validation or name is duplicate.
        """
        quickroll.trait_ids = await validate_trait_ids_from_mixed_sources(quickroll.trait_ids)

        if not quickroll.trait_ids:
            raise ValidationError(
                detail="Quick roll must have at least one trait",
                invalid_parameters=[
                    {
                        "field": "trait_ids",
                        "message": "Quick roll must have at least one trait",
                    },
                ],
            )

        existing_quickrolls = await QuickRoll.find(
            QuickRoll.user_id == quickroll.user_id,
            QuickRoll.is_archived == False,
            QuickRoll.id != quickroll.id,
            QuickRoll.name == quickroll.name,
        ).count()
        if existing_quickrolls > 0:
            raise ValidationError(
                detail="Quick roll name already exists",
                invalid_parameters=[
                    {
                        "field": "name",
                        "message": f"Quick roll name {quickroll.name} already exists",
                    },
                ],
            )
        return quickroll
