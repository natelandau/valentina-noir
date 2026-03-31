"""User service."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from vapi.constants import PermissionsGrantXP, UserRole
from vapi.db.models import Company, QuickRoll, User
from vapi.domain.handlers import UserArchiveHandler
from vapi.domain.utils import patch_document_from_dict, validate_trait_ids_from_mixed_sources
from vapi.lib.exceptions import PermissionDeniedError, ValidationError

from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

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
            requesting_user_id: The ID of the user requesting to manage the user.
            user_to_manage_id: The ID of the user to manage.

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

        Returns:
            User: The persisted user.
        """
        await user.save()
        company.user_ids.append(user.id)
        await company.save()
        return user

    @staticmethod
    def _build_user(
        data: UserPostDTO | UserRegisterDTO,
        *,
        company_id: PydanticObjectId,
        role: UserRole,
    ) -> User:
        """Build a User document from DTO fields.

        Args:
            data: The DTO containing user fields.
            company_id: The company to associate the user with.
            role: The role to assign.

        Returns:
            User: The constructed (unsaved) user document.
        """
        return User(
            name_first=data.name_first,
            name_last=data.name_last,
            username=data.username,
            email=data.email,
            role=role,
            company_id=company_id,
            discord_profile=data.discord_profile.model_dump(),
            google_profile=data.google_profile,
            github_profile=data.github_profile,
        )

    async def create_user(self, company: Company, data: UserPostDTO) -> User:
        """Create a user."""
        await self.validate_user_can_manage_user(
            requesting_user_id=data.requesting_user_id,
        )

        new_user = self._build_user(data, company_id=company.id, role=data.role)
        return await self._create_and_attach_user(company=company, user=new_user)

    async def register_user(self, company: Company, data: UserRegisterDTO) -> User:
        """Register a new user with the UNAPPROVED role.

        Designed for SSO onboarding where no existing Valentina user is making the
        request. Developer API key auth is sufficient - no requesting_user_id needed.

        Args:
            company: The company to register the user in.
            data: The registration data.
        """
        new_user = self._build_user(data, company_id=company.id, role=UserRole.UNAPPROVED)
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
        # Deferred import to break circular dependency: deps → controllers → services → deps
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


class UserXPService:
    """XP service."""

    async def _validate_user_can_grant_xp(
        self,
        company: Company,
        requesting_user_id: PydanticObjectId,
        target_user_id: PydanticObjectId,
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

    async def _apply_xp_operation(
        self,
        *,
        company: Company,
        requesting_user_id: PydanticObjectId,
        target_user: User,
        campaign_id: PydanticObjectId,
        amount: int,
        operation: Callable[[PydanticObjectId, int], Coroutine[None, None, CampaignExperience]],
    ) -> CampaignExperience:
        """Validate permissions, resolve the campaign, and apply an XP/CP operation.

        Args:
            company: The company context.
            requesting_user_id: The user performing the action.
            target_user: The user receiving the XP/CP change.
            campaign_id: The campaign to apply the change to.
            amount: The amount of XP/CP to add or remove.
            operation: The bound User method to call (e.g. ``target_user.add_xp``).

        Returns:
            CampaignExperience: The updated campaign experience.

        Raises:
            PermissionDeniedError: If the requesting user is not authorized.
        """
        _, campaign = await asyncio.gather(
            self._validate_user_can_grant_xp(
                company=company,
                requesting_user_id=requesting_user_id,
                target_user_id=target_user.id,
            ),
            GetModelByIdValidationService().get_campaign_by_id(campaign_id),
        )

        return await operation(campaign.id, amount)

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
        return await self._apply_xp_operation(
            company=company,
            requesting_user_id=requesting_user_id,
            target_user=target_user,
            campaign_id=campaign_id,
            amount=amount,
            operation=target_user.add_xp,
        )

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
        return await self._apply_xp_operation(
            company=company,
            requesting_user_id=requesting_user_id,
            target_user=target_user,
            campaign_id=campaign_id,
            amount=amount,
            operation=target_user.spend_xp,
        )

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
        return await self._apply_xp_operation(
            company=company,
            requesting_user_id=requesting_user_id,
            target_user=target_user,
            campaign_id=campaign_id,
            amount=amount,
            operation=target_user.add_cp,
        )
