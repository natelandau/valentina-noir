"""User service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vapi.constants import PermissionsGrantXP, UserRole
from vapi.db.models import Company, QuickRoll, User
from vapi.domain.handlers import UserArchiveHandler
from vapi.domain.utils import patch_document_from_dict, validate_trait_ids_from_mixed_sources
from vapi.lib.exceptions import PermissionDeniedError, ValidationError

from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from beanie import PydanticObjectId

    from vapi.db.models.user import CampaignExperience
    from vapi.domain.controllers.user.dto import UserPatchDTO, UserPostDTO, UserRegisterDTO


class UserService:
    """User service."""

    async def validate_user_can_manage_user(
        self,
        requesting_user_id: PydanticObjectId,
        user_to_manage_id: PydanticObjectId | None = None,
    ) -> None:
        """Validate if the user can manage the user.

        Args:
            user_to_manage_id: The ID of the user to manage.
            requesting_user_id: The ID of the user requesting to manage the user.

        Raises:
            ValidationError: If the requesting user is not found.
            PermissionDeniedError: If the requesting user is not authorized to manage the user.
        """
        if user_to_manage_id and requesting_user_id == user_to_manage_id:
            return

        requesting_user = await GetModelByIdValidationService().get_user_by_id(requesting_user_id)
        if requesting_user.role != UserRole.ADMIN:
            raise PermissionDeniedError(
                detail="Requesting user is not authorized to manage this user",
            )

    async def _create_and_attach_user(self, company: Company, user: User) -> User:
        """Persist a new user and add them to the company's user list.

        Args:
            company: The company the user belongs to.
            user: The user to persist.
        """
        await user.save()
        company.user_ids.append(user.id)
        await company.save()
        return user

    async def create_user(self, company: Company, data: UserPostDTO) -> User:
        """Create a user."""
        await self.validate_user_can_manage_user(
            requesting_user_id=data.requesting_user_id,
        )

        new_user = User(
            name_first=data.name_first,
            name_last=data.name_last,
            username=data.username,
            email=data.email,
            role=data.role,
            company_id=company.id,
            discord_profile=data.discord_profile,
            google_profile=data.google_profile,
            github_profile=data.github_profile,
        )
        return await self._create_and_attach_user(company=company, user=new_user)

    async def register_user(self, company: Company, data: UserRegisterDTO) -> User:
        """Register a new user with the UNAPPROVED role.

        Designed for SSO onboarding where no existing Valentina user is making the
        request. Developer API key auth is sufficient - no requesting_user_id needed.

        Args:
            company: The company to register the user in.
            data: The registration data.
        """
        new_user = User(
            name_first=data.name_first,
            name_last=data.name_last,
            username=data.username,
            email=data.email,
            role=UserRole.UNAPPROVED,
            company_id=company.id,
            discord_profile=data.discord_profile,
            google_profile=data.google_profile,
            github_profile=data.github_profile,
        )
        return await self._create_and_attach_user(company=company, user=new_user)

    async def merge_users(
        self,
        *,
        primary_user_id: PydanticObjectId,
        secondary_user_id: PydanticObjectId,
        company: Company,
        requesting_user_id: PydanticObjectId,
    ) -> User:
        """Merge an UNAPPROVED secondary user into an existing primary user.

        Resolve both users, copy OAuth profile fields from secondary to primary (only
        filling in empty fields), then archive the secondary user.

        Args:
            primary_user_id: The ID of the user account that survives.
            secondary_user_id: The ID of the UNAPPROVED user whose profile info is absorbed.
            company: The company both users belong to.
            requesting_user_id: The admin performing the merge.

        Raises:
            ValidationError: If the secondary user is not UNAPPROVED or users are the same.
            PermissionDeniedError: If the requesting user is not an admin.
        """
        import asyncio

        from vapi.domain import deps

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

        return primary_user

    @staticmethod
    def _absorb_profiles(*, primary: User, secondary: User) -> None:
        """Copy non-empty profile fields from secondary to primary where primary is empty.

        Args:
            primary: The target user whose empty profile fields get filled.
            secondary: The source user whose profile fields are copied.
        """
        for primary_profile, secondary_profile in (
            (primary.google_profile, secondary.google_profile),
            (primary.github_profile, secondary.github_profile),
            (primary.discord_profile, secondary.discord_profile),
        ):
            for field_name in secondary_profile.model_fields:
                secondary_value = getattr(secondary_profile, field_name)
                primary_value = getattr(primary_profile, field_name)
                if secondary_value is not None and primary_value is None:
                    setattr(primary_profile, field_name, secondary_value)

    async def update_user(self, user: User, data: UserPatchDTO) -> User:
        """Update a user."""
        await self.validate_user_can_manage_user(
            requesting_user_id=data.requesting_user_id,
            user_to_manage_id=user.id,
        )

        user = patch_document_from_dict(document=user, data=data.model_dump(exclude_unset=True))
        await user.save()

        return user

    async def remove_and_archive_user(self, *, user: User, company: Company) -> None:
        """Remove a user from the company and archive them.

        Args:
            user: The user to remove and archive.
            company: The company the user belongs to.
        """
        company.user_ids = [x for x in company.user_ids if x != user.id]
        await company.save()
        await UserArchiveHandler(user=user).handle()

    async def approve_user(
        self,
        *,
        user: User,
        role: UserRole,
        requesting_user_id: PydanticObjectId,
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
        requesting_user_id: PydanticObjectId,
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


class UserQuickRollService:
    """Quick roll service."""

    async def validate_quickroll(self, quickroll: QuickRoll) -> QuickRoll:
        """Validate a quick roll."""
        quickroll.trait_ids = await validate_trait_ids_from_mixed_sources(quickroll.trait_ids)

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


class UserXPService:
    """XP service."""

    async def _validate_user_can_grant_xp(
        self,
        company: Company,
        requesting_user_id: PydanticObjectId,
        target_user_id: PydanticObjectId,
    ) -> bool:
        """Validate if the user can grant XP."""
        requesting_user = await GetModelByIdValidationService().get_user_by_id(requesting_user_id)
        if (
            company.settings.permission_grant_xp == PermissionsGrantXP.UNRESTRICTED
            or requesting_user.role
            in [
                UserRole.STORYTELLER,
                UserRole.ADMIN,
            ]
        ):
            return True

        if (
            company.settings.permission_grant_xp == PermissionsGrantXP.PLAYER
            and requesting_user.id == target_user_id
        ):
            return True

        raise PermissionDeniedError(
            detail="User not authorized to grant or remove XP for this user"
        )

    async def add_xp_to_campaign_experience(
        self,
        *,
        company: Company,
        requesting_user_id: PydanticObjectId,
        target_user: User,
        campaign_id: PydanticObjectId,
        amount: int,
    ) -> CampaignExperience:
        """Add XP to a campaign experience."""
        await self._validate_user_can_grant_xp(
            company=company,
            requesting_user_id=requesting_user_id,
            target_user_id=target_user.id,
        )

        campaign = await GetModelByIdValidationService().get_campaign_by_id(campaign_id)
        return await target_user.add_xp(campaign_id=campaign.id, amount=amount)

    async def remove_xp_from_campaign_experience(
        self,
        *,
        company: Company,
        requesting_user_id: PydanticObjectId,
        target_user: User,
        campaign_id: PydanticObjectId,
        amount: int,
    ) -> CampaignExperience:
        """Remove XP from campaign experience."""
        await self._validate_user_can_grant_xp(
            company=company,
            requesting_user_id=requesting_user_id,
            target_user_id=target_user.id,
        )

        campaign = await GetModelByIdValidationService().get_campaign_by_id(campaign_id)
        return await target_user.spend_xp(campaign_id=campaign.id, amount=amount)

    async def add_cp_to_campaign_experience(
        self,
        *,
        company: Company,
        requesting_user_id: PydanticObjectId,
        target_user: User,
        campaign_id: PydanticObjectId,
        amount: int,
    ) -> CampaignExperience:
        """Add CP to a campaign experience."""
        await self._validate_user_can_grant_xp(
            company=company,
            requesting_user_id=requesting_user_id,
            target_user_id=target_user.id,
        )

        campaign = await GetModelByIdValidationService().get_campaign_by_id(campaign_id)
        return await target_user.add_cp(campaign_id=campaign.id, amount=amount)
