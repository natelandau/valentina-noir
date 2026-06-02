"""Tests for character count annotations."""

import pytest

from vapi.db.sql_models.character import Character
from vapi.domain.services.character_svc import annotate_character_counts

pytestmark = pytest.mark.anyio


async def test_character_counts_exact_with_fanout(
    company_factory,
    character_factory,
    character_inventory_factory,
    note_factory,
    s3asset_factory,
    user_factory,
):
    """Verify character counts stay exact when inventory, notes, and assets coexist."""
    # Given a character with 2 inventory items, 2 notes, and 2 assets
    company = await company_factory()
    character = await character_factory(company=company)
    uploader = await user_factory(company=company)
    await character_inventory_factory(character=character)
    await character_inventory_factory(character=character)
    await note_factory(company=company, character=character)
    await note_factory(company=company, character=character)
    await s3asset_factory(company=company, character=character, uploaded_by=uploader)
    await s3asset_factory(company=company, character=character, uploaded_by=uploader)

    # When the character counts are annotated
    annotated = await annotate_character_counts(Character.filter(id=character.id)).first()

    # Then every count is exact
    assert annotated.num_inventory_items == 2
    assert annotated.num_notes == 2
    assert annotated.num_assets == 2
