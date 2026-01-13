"""Campaign controller."""

from __future__ import annotations

from typing import Annotated

from litestar.controller import Controller
from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post, put
from litestar.params import Parameter
from pydantic import ValidationError as PydanticValidationError

from vapi.db.models import Campaign, Company
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CampaignService
from vapi.domain.utils import patch_internal_objects
from vapi.lib.guards import (
    developer_company_user_guard,
    user_storyteller_guard,
)
from vapi.openapi.tags import APITags
from vapi.utils.validation import raise_from_pydantic_validation_error

from . import dto


class CampaignController(Controller):
    """Campaign controller."""

    tags = [APITags.CAMPAIGNS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "campaign": Provide(deps.provide_campaign_by_id),
        "note": Provide(deps.provide_note_by_id),
    }
    guards = [developer_company_user_guard]
    return_dto = dto.CampaignDTO

    @get(
        path=urls.Campaigns.LIST,
        summary="List campaigns",
        operation_id="listCampaigns",
        description="Retrieve a paginated list of campaigns. Campaigns are containers for characters, books, chapters, etc.",
        cache=True,
    )
    async def list_campaigns(
        self,
        *,
        company: Company,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[Campaign]:
        """List all campaigns."""
        query = {
            "company_id": company.id,
            "is_archived": False,
        }
        count = await Campaign.find(query).count()
        campaigns = await Campaign.find(query).skip(offset).limit(limit).to_list()

        return OffsetPagination(items=campaigns, limit=limit, offset=offset, total=count)

    @get(
        path=urls.Campaigns.DETAIL,
        summary="Get campaign",
        operation_id="getCampaign",
        description="Retrieve detailed information about a specific campaign including desperation and danger levels.",
        cache=True,
    )
    async def get_campaign(self, *, campaign: Campaign) -> Campaign:
        """Get a campaign by ID."""
        return campaign

    @post(
        path=urls.Campaigns.CREATE,
        summary="Create campaign",
        operation_id="createCampaign",
        description="Create a new campaign. Requires storyteller privileges.",
        guards=[user_storyteller_guard],
        dto=dto.PostCampaignDTO,
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def create_campaign(
        self,
        *,
        company: Company,
        data: DTOData[Campaign],
    ) -> Campaign:
        """Create a campaign."""
        try:
            campaign_data = data.create_instance(company_id=company.id)
            campaign = Campaign(**campaign_data.model_dump(exclude_unset=True))
            await campaign.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return campaign

    @patch(
        path=urls.Campaigns.UPDATE,
        summary="Update campaign",
        operation_id="updateCampaign",
        description="Modify a campaign's properties. Only include fields that need to be changed. Requires storyteller privileges.",
        guards=[user_storyteller_guard],
        dto=dto.PatchCampaignDTO,
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def update_campaign(self, campaign: Campaign, data: DTOData[Campaign]) -> Campaign:
        """Update a campaign by ID."""
        campaign, data = await patch_internal_objects(original=campaign, data=data)
        updated_campaign = data.update_instance(campaign)
        try:
            await updated_campaign.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return updated_campaign

    @delete(
        path=urls.Campaigns.DELETE,
        summary="Delete campaign",
        operation_id="deleteCampaign",
        description="Remove a campaign from the system. Associated characters and content will no longer be accessible. Requires storyteller privileges.",
        guards=[user_storyteller_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def delete_campaign(self, campaign: Campaign) -> None:
        """Delete a campaign by ID."""
        campaign.is_archived = True
        await campaign.save()

    @put(
        path=urls.Campaigns.SET_DESPERATION,
        summary="Set desperation level",
        operation_id="setDesperationLevel",
        description="Update the campaign's desperation level.",
        guards=[user_storyteller_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def set_desperation(self, campaign: Campaign, desperation: int) -> Campaign:
        """Set desperation for a campaign."""
        service = CampaignService()
        campaign.desperation = service.validate_desperation_level(desperation)
        await campaign.save()
        return campaign

    @put(
        path=urls.Campaigns.SET_DANGER,
        summary="Set danger level",
        operation_id="setDangerLevel",
        description="Update the campaign's danger level.",
        guards=[user_storyteller_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def set_danger(self, campaign: Campaign, danger: int) -> Campaign:
        """Set danger for a campaign."""
        service = CampaignService()
        campaign.danger = service.validate_danger_level(danger)
        await campaign.save()
        return campaign
