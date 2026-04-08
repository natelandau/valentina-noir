"""Experience controller."""

from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get, post

from vapi.db.sql_models.campaign import Campaign
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain import deps, hooks, urls
from vapi.domain.services import UserXPService
from vapi.lib.guards import developer_company_user_guard, user_active_guard
from vapi.openapi.tags import APITags

from . import docs
from .dto import CampaignExperienceResponse, ExperienceAddRemove


class ExperienceController(Controller):
    """Experience controller."""

    tags = [APITags.EXPERIENCE.name, APITags.USERS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "campaign": Provide(deps.provide_campaign_by_id_for_experience),
    }
    guards = [developer_company_user_guard, user_active_guard]

    @get(
        path=urls.Users.EXPERIENCE_CAMPAIGN,
        summary="Get campaign experience",
        operation_id="getCampaignExperience",
        description=docs.GET_CAMPAIGN_EXPERIENCE_DESCRIPTION,
        cache=True,
    )
    async def get_campaign_experience(
        self, user: User, campaign: Campaign
    ) -> CampaignExperienceResponse:
        """Get campaign experience by user ID and campaign ID."""
        service = UserXPService()
        experience = await service.get_or_create_campaign_experience(user.id, campaign.id)
        return CampaignExperienceResponse.from_model(experience)

    @post(
        path=urls.Users.XP_ADD,
        summary="Add XP",
        operation_id="addXp",
        description=docs.ADD_XP_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def add_xp_to_campaign_experience(
        self, company: Company, user: User, data: ExperienceAddRemove
    ) -> CampaignExperienceResponse:
        """Add XP to campaign experience by user ID and campaign ID."""
        service = UserXPService()
        experience = await service.add_xp_to_campaign_experience(
            company=company,
            requesting_user_id=data.requesting_user_id,
            target_user=user,
            campaign_id=data.campaign_id,
            amount=data.amount,
        )
        return CampaignExperienceResponse.from_model(experience)

    @post(
        path=urls.Users.XP_REMOVE,
        summary="Remove XP",
        operation_id="removeXp",
        description=docs.REMOVE_XP_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def remove_xp_from_campaign_experience(
        self, company: Company, user: User, data: ExperienceAddRemove
    ) -> CampaignExperienceResponse:
        """Remove XP from campaign experience by user ID and campaign ID."""
        service = UserXPService()
        experience = await service.remove_xp_from_campaign_experience(
            company=company,
            requesting_user_id=data.requesting_user_id,
            target_user=user,
            campaign_id=data.campaign_id,
            amount=data.amount,
        )
        return CampaignExperienceResponse.from_model(experience)

    @post(
        path=urls.Users.CP_ADD,
        summary="Add cool points",
        operation_id="addCpToCampaignExperience",
        description=docs.ADD_CP_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def add_cp_to_campaign_experience(
        self, company: Company, user: User, data: ExperienceAddRemove
    ) -> CampaignExperienceResponse:
        """Add CP to campaign experience by user ID and campaign ID."""
        service = UserXPService()
        experience = await service.add_cp_to_campaign_experience(
            company=company,
            requesting_user_id=data.requesting_user_id,
            target_user=user,
            campaign_id=data.campaign_id,
            amount=data.amount,
        )
        return CampaignExperienceResponse.from_model(experience)
