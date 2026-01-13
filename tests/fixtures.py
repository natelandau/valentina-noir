"""Fixtures for testing."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pytest
from beanie.operators import In

from vapi.constants import GameVersion
from vapi.db.models import (
    Campaign,
    CampaignBook,
    CampaignChapter,
    Character,
    CharSheetSection,
    Company,
    Trait,
    TraitCategory,
    User,
)

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


@pytest.fixture
def build_url(
    base_company: Company,
    base_user: User,
    base_campaign: Campaign,
    base_character: Character,
    base_campaign_book: CampaignBook,
    base_campaign_chapter: CampaignChapter,
) -> Callable[[str, Any], str]:
    """Build a URL for the Developer."""

    def _build_url(url: str, **kwargs: Any) -> str:
        url = re.sub(r":[a-z]+}", "}", url, flags=re.IGNORECASE)
        replacements = {k: str(v) for k, v in kwargs.items()}

        if "company_id" not in replacements:
            replacements["company_id"] = str(base_company.id)

        if "user_id" not in replacements:
            replacements["user_id"] = str(base_user.id)

        if "campaign_id" not in replacements:
            replacements["campaign_id"] = str(base_campaign.id)

        if "character_id" not in replacements:
            replacements["character_id"] = str(base_character.id)

        if "game_version" not in replacements:
            replacements["game_version"] = GameVersion.V5.name

        if "book_id" not in replacements:
            replacements["book_id"] = str(base_campaign_book.id)

        if "chapter_id" not in replacements:
            replacements["chapter_id"] = str(base_campaign_chapter.id)

        return url.format(**replacements)

    return _build_url


@pytest.fixture
async def all_traits_in_section() -> Callable[[str], list[Trait]]:
    """Get all attribute traits."""

    async def _all_traits_in_section(section_name: str) -> list[Trait]:
        section = await CharSheetSection.find_one(CharSheetSection.name == section_name)
        categories = await TraitCategory.find(
            TraitCategory.parent_sheet_section_id == section.id,
            TraitCategory.is_archived == False,
        ).to_list()
        return await Trait.find(
            In(Trait.parent_category_id, [category.id for category in categories]),
            Trait.is_archived == False,
        ).to_list()

    return _all_traits_in_section


@pytest.fixture
async def all_traits_in_category() -> Callable[[str], list[Trait]]:
    """Get all traits in a category."""

    async def _all_traits_in_category(category_name: str) -> list[Trait]:
        category = await TraitCategory.find_one(TraitCategory.name == category_name)
        return await Trait.find(
            Trait.parent_category_id == category.id,
            Trait.is_archived == False,
        ).to_list()

    return _all_traits_in_category
