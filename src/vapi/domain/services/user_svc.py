"""User service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vapi.constants import PermissionsGrantXP, UserRole
from vapi.db.models import Company, QuickRoll, User
from vapi.domain.utils import validate_trait_ids_from_mixed_sources
from vapi.lib.exceptions import PermissionDeniedError, ValidationError

from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from beanie import PydanticObjectId

    from vapi.db.models.user import CampaignExperience


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
        self, company: Company, requesting_user: User, target_user_id: PydanticObjectId
    ) -> bool:
        """Validate if the user can grant XP."""
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
        requesting_user: User,
        target_user_id: PydanticObjectId,
        campaign_id: PydanticObjectId,
        amount: int,
    ) -> CampaignExperience:
        """Add XP to a campaign experience."""
        await self._validate_user_can_grant_xp(
            company=company,
            requesting_user=requesting_user,
            target_user_id=target_user_id,
        )

        target_user = await GetModelByIdValidationService().get_user_by_id(target_user_id)
        campaign = await GetModelByIdValidationService().get_campaign_by_id(campaign_id)
        return await target_user.add_xp(campaign_id=campaign.id, amount=amount)

    async def remove_xp_from_campaign_experience(
        self,
        *,
        company: Company,
        requesting_user: User,
        target_user_id: PydanticObjectId,
        campaign_id: PydanticObjectId,
        amount: int,
    ) -> CampaignExperience:
        """Remove XP from campaign experience."""
        await self._validate_user_can_grant_xp(
            company=company,
            requesting_user=requesting_user,
            target_user_id=target_user_id,
        )

        target_user = await GetModelByIdValidationService().get_user_by_id(target_user_id)
        campaign = await GetModelByIdValidationService().get_campaign_by_id(campaign_id)
        return await target_user.spend_xp(campaign_id=campaign.id, amount=amount)

    async def add_cp_to_campaign_experience(
        self,
        *,
        company: Company,
        requesting_user: User,
        target_user_id: PydanticObjectId,
        campaign_id: PydanticObjectId,
        amount: int,
    ) -> CampaignExperience:
        """Add CP to a campaign experience."""
        await self._validate_user_can_grant_xp(
            company=company,
            requesting_user=requesting_user,
            target_user_id=target_user_id,
        )

        target_user = await GetModelByIdValidationService().get_user_by_id(target_user_id)
        campaign = await GetModelByIdValidationService().get_campaign_by_id(campaign_id)
        return await target_user.add_cp(campaign_id=campaign.id, amount=amount)
