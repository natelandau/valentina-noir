"""Unit tests for CampaignResponse DTO."""

from typing import TYPE_CHECKING, Any

import msgspec
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


async def test_campaign_response_serializes_year(
    campaign_factory: "Callable[..., Any]",
    company_factory: "Callable[..., Any]",
) -> None:
    """Verify CampaignResponse carries a free-form year through JSON round-trip."""
    from vapi.db.sql_models.campaign import Campaign
    from vapi.domain.controllers.campaign.dto import CampaignResponse
    from vapi.domain.services.campaign_svc import annotate_campaign_counts

    # Given a campaign with a year
    company = await company_factory()
    campaign = await campaign_factory(company=company, year="1888")
    annotated = await annotate_campaign_counts(Campaign.filter(id=campaign.id)).first()

    # When building the response DTO and round-tripping through JSON
    response = CampaignResponse.from_model(annotated)
    decoded = msgspec.json.decode(msgspec.json.encode(response), type=CampaignResponse)

    # Then the year survives serialization
    assert decoded.year == "1888"


async def test_campaign_response_allows_null_year(
    campaign_factory: "Callable[..., Any]",
    company_factory: "Callable[..., Any]",
) -> None:
    """Verify CampaignResponse serializes a campaign with no year as null."""
    from vapi.db.sql_models.campaign import Campaign
    from vapi.domain.controllers.campaign.dto import CampaignResponse
    from vapi.domain.services.campaign_svc import annotate_campaign_counts

    # Given a campaign with no year
    company = await company_factory()
    campaign = await campaign_factory(company=company)
    annotated = await annotate_campaign_counts(Campaign.filter(id=campaign.id)).first()

    # When building the response DTO and round-tripping through JSON
    # (msgspec only validates types on decode, so the round-trip proves nullability)
    response = CampaignResponse.from_model(annotated)
    decoded = msgspec.json.decode(msgspec.json.encode(response), type=CampaignResponse)

    # Then the year is None after surviving JSON decode validation
    assert decoded.year is None
