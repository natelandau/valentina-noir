"""Unit tests for TraitCategoryResponse and TraitSubcategoryResponse."""

import msgspec
import pytest

from vapi.db.sql_models.character_sheet import TraitCategory, TraitSubcategory
from vapi.domain.controllers.character_blueprint.dto import (
    TraitCategoryResponse,
    TraitSubcategoryResponse,
)

pytestmark = pytest.mark.anyio


async def test_category_response_names_its_sheet_section() -> None:
    """Verify a category always carries its sheet section's ID and name."""
    # Given a seeded category with its sheet section loaded
    category = (
        await TraitCategory.filter(is_archived=False).first().prefetch_related("sheet_section")
    )

    # When the response is built and round-tripped through JSON
    response = TraitCategoryResponse.from_model(category)
    decoded = msgspec.json.decode(msgspec.json.encode(response), type=TraitCategoryResponse)

    # Then the sheet section is named
    assert decoded.sheet_section_id == category.sheet_section.id
    assert decoded.sheet_section_name == category.sheet_section.name


async def test_subcategory_response_names_its_category() -> None:
    """Verify a subcategory always carries its parent category's ID and name."""
    # Given a seeded subcategory with its relations loaded
    subcategory = (
        await TraitSubcategory.filter(is_archived=False)
        .first()
        .prefetch_related("category", "sheet_section")
    )

    # When the response is built and round-tripped through JSON
    response = TraitSubcategoryResponse.from_model(subcategory)
    decoded = msgspec.json.decode(msgspec.json.encode(response), type=TraitSubcategoryResponse)

    # Then the parent category is named
    assert decoded.category_id == subcategory.category.id
    assert decoded.category_name == subcategory.category.name
