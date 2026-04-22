"""Unit tests for pre_save signal handlers that titlecase name fields."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.character_sheet import Trait

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any


TITLECASE_CASES = [
    ("hawk's nest", "Hawk's Nest"),
    ("the letter of the law", "The Letter of the Law"),
    ("LOUD NAME", "Loud Name"),
    ("already Titled Name", "Already Titled Name"),
]


class TestTraitNameSignal:
    """Tests for normalize_trait_name pre_save signal."""

    @pytest.mark.parametrize(("raw", "expected"), TITLECASE_CASES)
    async def test_trait_name_titlecased_on_create(
        self,
        trait_factory: Callable[..., Any],
        raw: str,
        expected: str,
    ) -> None:
        """Verify Trait.name is titlecased via pre_save signal on create."""
        # Given / When a trait is created with a non-canonical name
        trait = await trait_factory(name=raw)

        # Then the persisted name matches titlecase output
        refreshed = await Trait.get(id=trait.id)
        assert refreshed.name == expected

    async def test_trait_name_titlecased_on_update(self, trait_factory: Callable[..., Any]) -> None:
        """Verify Trait.name is titlecased via pre_save signal on update."""
        # Given an existing trait
        trait = await trait_factory(name="Original Name")

        # When the name is updated with apostrophe content
        trait.name = "hawk's nest"
        await trait.save()

        # Then the persisted value is titlecased preserving the apostrophe
        refreshed = await Trait.get(id=trait.id)
        assert refreshed.name == "Hawk's Nest"


class TestCampaignNameSignal:
    """Tests for normalize_campaign_name pre_save signal."""

    @pytest.mark.parametrize(("raw", "expected"), TITLECASE_CASES)
    async def test_campaign_name_titlecased_on_create(
        self,
        campaign_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
        raw: str,
        expected: str,
    ) -> None:
        """Verify Campaign.name is titlecased via pre_save signal on create."""
        # Given a company (required FK)
        company = await company_factory()

        # When a campaign is created with a non-canonical name
        campaign = await campaign_factory(company=company, name=raw)

        # Then the persisted name matches titlecase output
        refreshed = await Campaign.get(id=campaign.id)
        assert refreshed.name == expected

    async def test_campaign_name_titlecased_on_update(
        self,
        campaign_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify Campaign.name is titlecased via pre_save signal on update."""
        # Given an existing campaign
        company = await company_factory()
        campaign = await campaign_factory(company=company, name="Original Name")

        # When the name is updated
        campaign.name = "hawk's nest"
        await campaign.save()

        # Then the persisted value is titlecased preserving the apostrophe
        refreshed = await Campaign.get(id=campaign.id)
        assert refreshed.name == "Hawk's Nest"


class TestCampaignBookNameSignal:
    """Tests for normalize_campaign_book_name pre_save signal."""

    @pytest.mark.parametrize(("raw", "expected"), TITLECASE_CASES)
    async def test_campaign_book_name_titlecased_on_create(
        self,
        campaign_book_factory: Callable[..., Any],
        campaign_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
        raw: str,
        expected: str,
    ) -> None:
        """Verify CampaignBook.name is titlecased via pre_save signal on create."""
        # Given a campaign
        company = await company_factory()
        campaign = await campaign_factory(company=company)

        # When a book is created with a non-canonical name
        book = await campaign_book_factory(campaign=campaign, name=raw)

        # Then the persisted name matches titlecase output
        refreshed = await CampaignBook.get(id=book.id)
        assert refreshed.name == expected


class TestCampaignChapterNameSignal:
    """Tests for normalize_campaign_chapter_name pre_save signal."""

    @pytest.mark.parametrize(("raw", "expected"), TITLECASE_CASES)
    async def test_campaign_chapter_name_titlecased_on_create(
        self,
        campaign_chapter_factory: Callable[..., Any],
        campaign_book_factory: Callable[..., Any],
        campaign_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
        raw: str,
        expected: str,
    ) -> None:
        """Verify CampaignChapter.name is titlecased via pre_save signal on create."""
        # Given a book
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(campaign=campaign)

        # When a chapter is created with a non-canonical name
        chapter = await campaign_chapter_factory(book=book, name=raw)

        # Then the persisted name matches titlecase output
        refreshed = await CampaignChapter.get(id=chapter.id)
        assert refreshed.name == expected
