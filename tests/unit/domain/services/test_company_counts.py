"""Tests for company count annotations (fan-out correctness)."""

import pytest

from vapi.constants import CharacterType
from vapi.db.sql_models.company import Company
from vapi.domain.services.company_svc import annotate_company_counts

pytestmark = pytest.mark.anyio


async def test_company_counts_no_fanout(
    company_factory, campaign_factory, user_factory, character_factory
):
    """Verify num_campaigns, num_users, and character counts are not inflated when relations coexist on the same company."""
    # Given a company with 2 campaigns, 2 users, and 1 player character (fan-out would multiply them)
    company = await company_factory()
    campaign = await campaign_factory(company=company)
    await campaign_factory(company=company)
    user_one = await user_factory(company=company)
    user_two = await user_factory(company=company)
    # Reuse the existing campaign and users so the character adds no new campaigns or users
    await character_factory(
        company=company,
        campaign=campaign,
        user_creator=user_one,
        user_player=user_two,
        type=CharacterType.PLAYER,
    )

    # When the counts are annotated
    annotated = await annotate_company_counts(Company.filter(id=company.id)).first()

    # Then each count is exact, not inflated by the cross join
    assert annotated.num_campaigns == 2
    assert annotated.num_users == 2
    assert annotated.num_player_characters == 1
    assert annotated.num_storyteller_characters == 0
    assert annotated.num_npc_characters == 0
