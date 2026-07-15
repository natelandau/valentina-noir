"""User XP service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise.expressions import F

from vapi.constants import COOL_POINT_VALUE, PermissionsGrantXP, UserRole
from vapi.db.sql_models.user import CampaignExperience, User
from vapi.lib.exceptions import NotEnoughXPError, PermissionDeniedError

from .user_svc import UserService
from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from uuid import UUID

    from vapi.db.sql_models.company import Company


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
        acting_user_id: UUID,
        target_user_id: UUID,
    ) -> None:
        """Validate if the user can grant XP.

        Raises:
            PermissionDeniedError: If the user is not authorized to grant XP.
        """
        requesting_user = await GetModelByIdValidationService().get_user_by_id(acting_user_id)
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
        acting_user_id: UUID,
        target_user: User,
        campaign_id: UUID,
        amount: int,
    ) -> CampaignExperience:
        """Add XP to a campaign experience with permission validation."""
        await UserService()._assert_requester_active(acting_user_id)  # noqa: SLF001
        await self._validate_user_can_grant_xp(
            company=company,
            acting_user_id=acting_user_id,
            target_user_id=target_user.id,
        )
        return await self.add_xp(target_user.id, campaign_id, amount)

    async def remove_xp_from_campaign_experience(
        self,
        *,
        company: Company,
        acting_user_id: UUID,
        target_user: User,
        campaign_id: UUID,
        amount: int,
    ) -> CampaignExperience:
        """Remove XP from a campaign experience with permission validation."""
        await UserService()._assert_requester_active(acting_user_id)  # noqa: SLF001
        await self._validate_user_can_grant_xp(
            company=company,
            acting_user_id=acting_user_id,
            target_user_id=target_user.id,
        )
        return await self.spend_xp(target_user.id, campaign_id, amount)

    async def add_cp_to_campaign_experience(
        self,
        *,
        company: Company,
        acting_user_id: UUID,
        target_user: User,
        campaign_id: UUID,
        amount: int,
    ) -> CampaignExperience:
        """Add cool points to a campaign experience with permission validation."""
        await UserService()._assert_requester_active(acting_user_id)  # noqa: SLF001
        await self._validate_user_can_grant_xp(
            company=company,
            acting_user_id=acting_user_id,
            target_user_id=target_user.id,
        )
        return await self.add_cp(target_user.id, campaign_id, amount)
