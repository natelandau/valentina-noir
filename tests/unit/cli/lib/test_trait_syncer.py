"""Unit tests for TraitSyncer."""

import pytest

from vapi.cli.lib.trait_syncer import TraitSyncer
from vapi.db.sql_models.character_sheet import CharSheetSection, Trait

pytestmark = pytest.mark.anyio


async def test_sync_trait_leaves_a_characters_custom_trait_untouched(
    trait_category_factory, trait_factory, character_factory, company_factory
):
    """Verify seeding a fixture trait never overwrites a character's same-named custom trait."""
    # Given a character with a custom trait whose name a fixture also uses
    company = await company_factory()
    character = await character_factory(company=company)
    category = await trait_category_factory(name="ZZ Syncer Category")
    section = await CharSheetSection.get(id=category.sheet_section_id)
    custom_trait = await trait_factory(
        name="Cryptography",
        category=category,
        sheet_section=section,
        custom_for_character_id=character.id,
        description="The character's own hard-won skill",
        initial_cost=7,
    )

    # When the seeder syncs a fixture trait of the same name into the same category
    syncer = TraitSyncer()
    syncer._traits_fast_path = False
    await syncer._sync_trait(
        {"name": "Cryptography", "description": "Fixture description", "initial_cost": 1},
        category=category,
        section=section,
    )

    # Then the character's custom trait is unchanged
    await custom_trait.refresh_from_db()
    assert custom_trait.description == "The character's own hard-won skill"
    assert custom_trait.initial_cost == 7
    assert str(custom_trait.custom_for_character_id) == str(character.id)

    # And the fixture trait is seeded as a separate global trait
    seeded = await Trait.filter(
        name="Cryptography", category_id=category.id, custom_for_character_id__isnull=True
    ).first()
    assert seeded is not None
    assert seeded.description == "Fixture description"
    await seeded.delete()
