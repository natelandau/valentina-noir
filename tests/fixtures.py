"""Fixtures for testing."""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Any

import pytest

from vapi.constants import GameVersion
from vapi.db.sql_models.character_sheet import CharSheetSection, Trait, TraitCategory

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


@pytest.fixture
def build_url() -> Callable[[str, Any], str]:
    """Build a URL for tests using dummy default IDs.

    Default IDs are stable dummy UUIDs used as fallbacks when the caller does
    not supply explicit IDs. Integration tests always pass real IDs via kwargs,
    so these defaults exist only to satisfy the str.format() substitution when
    a URL template contains placeholder keys the caller did not override.
    """

    def _build_url(url: str, **kwargs: Any) -> str:
        url = re.sub(r":[a-z]+}", "}", url, flags=re.IGNORECASE)
        defaults = {
            "company_id": str(uuid.UUID("00000000-0000-0000-0000-000000000001")),
            "user_id": str(uuid.UUID("00000000-0000-0000-0000-000000000002")),
            "campaign_id": str(uuid.UUID("00000000-0000-0000-0000-000000000003")),
            "character_id": str(uuid.UUID("00000000-0000-0000-0000-000000000004")),
            "game_version": GameVersion.V5.name,
            "book_id": str(uuid.UUID("00000000-0000-0000-0000-000000000005")),
            "chapter_id": str(uuid.UUID("00000000-0000-0000-0000-000000000006")),
        }
        replacements = defaults | {k: str(v) for k, v in kwargs.items()}
        return url.format(**replacements)

    return _build_url


@pytest.fixture
async def all_traits_in_section() -> Callable[[str], list[Trait]]:
    """Get all attribute traits."""

    async def _all_traits_in_section(section_name: str) -> list[Trait]:
        section = await CharSheetSection.filter(name=section_name).first()
        categories = await TraitCategory.filter(
            section=section,
            is_archived=False,
        ).all()
        return await Trait.filter(
            category_id__in=[c.id for c in categories],
            is_archived=False,
        ).all()

    return _all_traits_in_section


@pytest.fixture
async def all_traits_in_category() -> Callable[[str], list[Trait]]:
    """Get all traits in a category."""

    async def _all_traits_in_category(category_name: str) -> list[Trait]:
        category = await TraitCategory.filter(name=category_name).first()
        return await Trait.filter(
            category=category,
            is_archived=False,
        ).all()

    return _all_traits_in_category
