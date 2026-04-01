"""Campaign controller."""

import asyncio
from typing import Annotated

import msgspec
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.sql_models.campaign import Campaign
from vapi.db.sql_models.company import Company
from vapi.domain import hooks, pg_deps, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CampaignService
from vapi.lib.pg_guards import pg_developer_company_user_guard
from vapi.openapi.tags import APITags

from . import docs
from .dto import CampaignCreate, CampaignPatch, CampaignResponse
from .guards import user_can_manage_campaign


class CampaignController(Controller):
    """Campaign controller."""

    tags = [APITags.CAMPAIGNS.name]
    dependencies = {
        "company": Provide(pg_deps.provide_pg_company_by_id),
        "user": Provide(pg_deps.provide_user_by_id_and_company),
        "campaign": Provide(pg_deps.provide_campaign_by_id),
        "developer": Provide(pg_deps.provide_developer_from_request),
    }
    guards = [pg_developer_company_user_guard]

    @get(
        path=urls.Campaigns.LIST,
        summary="List campaigns",
        operation_id="listCampaigns",
        description=docs.LIST_CAMPAIGNS_DESCRIPTION,
        cache=True,
    )
    async def list_campaigns(
        self,
        *,
        company: Company,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[CampaignResponse]:
        """List all campaigns."""
        qs = Campaign.filter(company_id=company.id, is_archived=False)
        count, campaigns = await asyncio.gather(
            qs.count(),
            qs.offset(offset).limit(limit),
        )
        return OffsetPagination(
            items=[CampaignResponse.from_model(c) for c in campaigns],
            limit=limit,
            offset=offset,
            total=count,
        )

    @get(
        path=urls.Campaigns.DETAIL,
        summary="Get campaign",
        operation_id="getCampaign",
        description=docs.GET_CAMPAIGN_DESCRIPTION,
        cache=True,
    )
    async def get_campaign(self, *, campaign: Campaign) -> CampaignResponse:
        """Get a campaign by ID."""
        return CampaignResponse.from_model(campaign)

    @post(
        path=urls.Campaigns.CREATE,
        summary="Create campaign",
        operation_id="createCampaign",
        description=docs.CREATE_CAMPAIGN_DESCRIPTION,
        guards=[user_can_manage_campaign],
        after_response=hooks.post_data_update_hook,
    )
    async def create_campaign(
        self,
        *,
        company: Company,
        data: CampaignCreate,
    ) -> CampaignResponse:
        """Create a campaign."""
        campaign = await Campaign.create(
            name=data.name,
            description=data.description,
            desperation=data.desperation,
            danger=data.danger,
            company=company,
        )
        return CampaignResponse.from_model(campaign)

    @patch(
        path=urls.Campaigns.UPDATE,
        summary="Update campaign",
        operation_id="updateCampaign",
        description=docs.UPDATE_CAMPAIGN_DESCRIPTION,
        guards=[user_can_manage_campaign],
        after_response=hooks.post_data_update_hook,
    )
    async def update_campaign(self, campaign: Campaign, data: CampaignPatch) -> CampaignResponse:
        """Update a campaign by ID."""
        if not isinstance(data.name, msgspec.UnsetType):
            campaign.name = data.name
        if not isinstance(data.description, msgspec.UnsetType):
            campaign.description = data.description
        if not isinstance(data.desperation, msgspec.UnsetType):
            campaign.desperation = data.desperation
        if not isinstance(data.danger, msgspec.UnsetType):
            campaign.danger = data.danger
        await campaign.save()
        return CampaignResponse.from_model(campaign)

    @delete(
        path=urls.Campaigns.DELETE,
        summary="Delete campaign",
        operation_id="deleteCampaign",
        description=docs.DELETE_CAMPAIGN_DESCRIPTION,
        guards=[user_can_manage_campaign],
        after_response=hooks.post_data_update_hook,
    )
    async def delete_campaign(self, campaign: Campaign) -> None:
        """Delete a campaign by ID."""
        service = CampaignService()
        await service.archive_campaign(campaign)
