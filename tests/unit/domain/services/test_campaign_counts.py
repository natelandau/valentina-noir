"""Tests for campaign/book/chapter count annotations."""

import pytest

from vapi.db.sql_models.campaign import Campaign
from vapi.domain.services.campaign_svc import annotate_campaign_counts

pytestmark = pytest.mark.anyio


async def test_campaign_counts_exact_with_fanout(
    company_factory,
    campaign_factory,
    campaign_book_factory,
    campaign_chapter_factory,
    character_factory,
    note_factory,
):
    """Verify campaign counts stay exact when books, chapters, notes, and characters coexist."""
    # Given a campaign with 2 books (3 chapters total), 2 notes, and 2 characters
    company = await company_factory()
    campaign = await campaign_factory(company=company)
    book1 = await campaign_book_factory(campaign=campaign)
    book2 = await campaign_book_factory(campaign=campaign)
    await campaign_chapter_factory(book=book1)
    await campaign_chapter_factory(book=book1)
    await campaign_chapter_factory(book=book2)
    await note_factory(company=company, campaign=campaign)
    await note_factory(company=company, campaign=campaign)
    await character_factory(company=company, campaign=campaign)
    await character_factory(company=company, campaign=campaign)

    # When the campaign counts are annotated
    annotated = await annotate_campaign_counts(Campaign.filter(id=campaign.id)).first()

    # Then every count is exact
    assert annotated.num_books == 2
    assert annotated.num_chapters == 3
    assert annotated.num_notes == 2
    assert annotated.num_characters == 2


async def test_campaign_counts_exclude_archived(
    company_factory,
    campaign_factory,
    campaign_book_factory,
):
    """Verify archived children are not counted."""
    # Given a campaign with one active and one archived book
    company = await company_factory()
    campaign = await campaign_factory(company=company)
    await campaign_book_factory(campaign=campaign)
    await campaign_book_factory(campaign=campaign, is_archived=True)

    # When counts are annotated
    annotated = await annotate_campaign_counts(Campaign.filter(id=campaign.id)).first()

    # Then the archived book is excluded
    assert annotated.num_books == 1
