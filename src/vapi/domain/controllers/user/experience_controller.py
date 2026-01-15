"""Experience controller."""

from __future__ import annotations

from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get, post

from vapi.db.models import Campaign, Company, User  # noqa: TC001
from vapi.db.models.user import CampaignExperience  # noqa: TC001
from vapi.domain import deps, hooks, urls
from vapi.domain.services import UserXPService
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import dto


class ExperienceController(Controller):
    """Experience controller."""

    tags = [APITags.EXPERIENCE.name, APITags.USERS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "campaign": Provide(deps.provide_campaign_by_id),
    }
    guards = [developer_company_user_guard]
    return_dto = dto.ReturnCampaignExperienceDTO

    @get(
        path=urls.Users.EXPERIENCE_CAMPAIGN,
        summary="Get campaign experience",
        operation_id="getCampaignExperience",
        description="Retrieve a user's experience points and cool points for a specific campaign. Creates the experience record if it doesn't exist.",
        cache=True,
    )
    async def get_campaign_experience(self, user: User, campaign: Campaign) -> CampaignExperience:
        """Get campaign experience by user ID and campaign ID."""
        return await user.get_or_create_campaign_experience(campaign.id)

    @post(
        path=urls.Users.XP_ADD,
        summary="Add XP",
        operation_id="addXp",
        description="Award experience points to a user for a specific campaign. The XP is added to both current and total XP pools.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def add_xp_to_campaign_experience(
        self, company: Company, user: User, data: dto.ExperienceAddRemove
    ) -> CampaignExperience:
        """Add XP to campaign experience by user ID and campaign ID."""
        service = UserXPService()
        return await service.add_xp_to_campaign_experience(
            company=company,
            requesting_user=user,
            target_user_id=data.user_id,
            campaign_id=data.campaign_id,
            amount=data.amount,
        )

    @post(
        path=urls.Users.XP_REMOVE,
        summary="Remove XP",
        operation_id="removeXp",
        description="Deduct experience points from a user's current XP pool. Returns an error if the user has insufficient XP.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def remove_xp_from_campaign_experience(
        self, company: Company, user: User, data: dto.ExperienceAddRemove
    ) -> CampaignExperience:
        """Remove XP from campaign experience by user ID and campaign ID."""
        service = UserXPService()
        return await service.remove_xp_from_campaign_experience(
            company=company,
            requesting_user=user,
            target_user_id=data.user_id,
            campaign_id=data.campaign_id,
            amount=data.amount,
        )

    @post(
        path=urls.Users.CP_ADD,
        summary="Add cool points",
        operation_id="addCpToCampaignExperience",
        description="Award cool points to a user for a specific campaign. Cool points are converted to XP automatically based on the configured exchange rate.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def add_cp_to_campaign_experience(
        self, company: Company, user: User, data: dto.ExperienceAddRemove
    ) -> CampaignExperience:
        """Add CP to campaign experience by user ID and campaign ID."""
        service = UserXPService()
        return await service.add_cp_to_campaign_experience(
            company=company,
            requesting_user=user,
            target_user_id=data.user_id,
            campaign_id=data.campaign_id,
            amount=data.amount,
        )
