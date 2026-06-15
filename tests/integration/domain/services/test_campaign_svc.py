"""Test the campaign service character validation."""

from collections.abc import Callable

import pytest

from vapi.db.sql_models.campaign import Campaign
from vapi.db.sql_models.character import Character
from vapi.db.sql_models.company import Company
from vapi.domain.services.campaign_svc import CampaignService
from vapi.lib.exceptions import ValidationError

pytestmark = pytest.mark.anyio


async def test_validate_campaign_characters_returns_active_in_campaign(
    session_company: Company,
    campaign_factory: Callable[..., Campaign],
    character_factory: Callable[..., Character],
) -> None:
    """Verify valid in-campaign character IDs are returned."""
    # Given a campaign with two active characters
    campaign = await campaign_factory(company=session_company)
    char_a = await character_factory(company=session_company, campaign=campaign)
    char_b = await character_factory(company=session_company, campaign=campaign)

    # When validating those IDs
    result = await CampaignService().validate_campaign_characters(
        character_ids=[char_a.id, char_b.id], campaign_id=campaign.id
    )

    # Then both characters are returned
    assert {c.id for c in result} == {char_a.id, char_b.id}


async def test_validate_campaign_characters_rejects_other_campaign(
    session_company: Company,
    campaign_factory: Callable[..., Campaign],
    character_factory: Callable[..., Character],
) -> None:
    """Verify a character from another campaign is rejected."""
    # Given a character in a different campaign
    campaign = await campaign_factory(company=session_company)
    other_campaign = await campaign_factory(company=session_company)
    foreign = await character_factory(company=session_company, campaign=other_campaign)

    # When validating it against the first campaign
    # Then a ValidationError is raised
    with pytest.raises(ValidationError):
        await CampaignService().validate_campaign_characters(
            character_ids=[foreign.id], campaign_id=campaign.id
        )


async def test_validate_campaign_characters_rejects_archived(
    session_company: Company,
    campaign_factory: Callable[..., Campaign],
    character_factory: Callable[..., Character],
) -> None:
    """Verify an archived character is rejected."""
    # Given an archived character in the campaign
    campaign = await campaign_factory(company=session_company)
    archived = await character_factory(company=session_company, campaign=campaign, is_archived=True)

    # When validating it
    # Then a ValidationError is raised
    with pytest.raises(ValidationError):
        await CampaignService().validate_campaign_characters(
            character_ids=[archived.id], campaign_id=campaign.id
        )


async def test_validate_campaign_characters_empty_returns_empty(
    session_company: Company,
    campaign_factory: Callable[..., Campaign],
) -> None:
    """Verify an empty ID list short-circuits to an empty result."""
    # Given a campaign
    campaign = await campaign_factory(company=session_company)

    # When validating an empty list
    result = await CampaignService().validate_campaign_characters(
        character_ids=[], campaign_id=campaign.id
    )

    # Then the result is empty
    assert result == []


async def test_validate_campaign_characters_deduplicates_ids(
    session_company: Company,
    campaign_factory: Callable[..., Campaign],
    character_factory: Callable[..., Character],
) -> None:
    """Verify duplicate IDs in the input are collapsed to a single result entry."""
    # Given a campaign with one character
    campaign = await campaign_factory(company=session_company)
    char = await character_factory(company=session_company, campaign=campaign)

    # When the same ID is submitted twice
    result = await CampaignService().validate_campaign_characters(
        character_ids=[char.id, char.id], campaign_id=campaign.id
    )

    # Then exactly one character object is returned
    assert len(result) == 1
    assert result[0].id == char.id


async def test_validate_campaign_characters_rejects_mixed_validity(
    session_company: Company,
    campaign_factory: Callable[..., Campaign],
    character_factory: Callable[..., Character],
) -> None:
    """Verify one valid and one cross-campaign ID together are rejected."""
    # Given a valid in-campaign character and a character in another campaign
    campaign = await campaign_factory(company=session_company)
    other_campaign = await campaign_factory(company=session_company)
    valid = await character_factory(company=session_company, campaign=campaign)
    foreign = await character_factory(company=session_company, campaign=other_campaign)

    # When validating the two together against the first campaign
    # Then a ValidationError is raised
    with pytest.raises(ValidationError):
        await CampaignService().validate_campaign_characters(
            character_ids=[valid.id, foreign.id], campaign_id=campaign.id
        )
