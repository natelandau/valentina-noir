"""Unit tests for TraitSyncer."""

import pytest

from vapi.cli.lib.trait_syncer import TraitSyncer
from vapi.constants import TrackerType
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


async def test_sync_trait_creates_trait_with_tracker_types(trait_category_factory):
    """Verify syncing a fixture row with tracker keys stores them on a new trait."""
    # Given a category and a fixture row carrying tracker types
    category = await trait_category_factory(name="ZZ Tracker Category")
    section = await CharSheetSection.get(id=category.sheet_section_id)

    # When the syncer creates the trait
    syncer = TraitSyncer()
    syncer._traits_fast_path = False
    trait, created, _ = await syncer._sync_trait(
        {"name": "ZZ Tracked", "tracker_type_v4": "COUNTER", "tracker_type_v5": "DAMAGE"},
        category=category,
        section=section,
    )

    # Then the stored trait carries both tracker types
    stored = await Trait.get(id=trait.id)
    try:
        assert created
        assert stored.tracker_type_v4 == TrackerType.COUNTER
        assert stored.tracker_type_v5 == TrackerType.DAMAGE
    finally:
        await stored.delete()


async def test_sync_trait_updates_existing_trait_with_tracker_types(
    trait_category_factory, trait_factory
):
    """Verify syncing a fixture row with tracker keys updates a trait that had none."""
    # Given an existing global trait without tracker types
    category = await trait_category_factory(name="ZZ Tracker Update Category")
    section = await CharSheetSection.get(id=category.sheet_section_id)
    existing = await trait_factory(name="ZZ Tracked", category=category, sheet_section=section)

    # When the syncer processes a fixture row that now carries tracker types
    syncer = TraitSyncer()
    syncer._traits_fast_path = False
    _, created, updated = await syncer._sync_trait(
        {"name": "ZZ Tracked", "tracker_type_v4": None, "tracker_type_v5": "STAINS"},
        category=category,
        section=section,
    )

    # Then the existing row gains the tracker type
    assert not created
    assert updated
    await existing.refresh_from_db()
    assert existing.tracker_type_v4 is None
    assert existing.tracker_type_v5 == TrackerType.STAINS
