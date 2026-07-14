"""Unit tests for TraitPowerSyncer."""

import pytest

from vapi.cli.lib.trait_power_syncer import TraitPowerSyncer
from vapi.db.sql_models.character_sheet import TraitPower

pytestmark = pytest.mark.anyio


async def test_syncer_creates_powers_for_resolved_trait(trait_category_factory, trait_factory):
    """Verify the syncer resolves a trait by name+category and creates its powers."""
    # Given a category and its trait matching a fixture entry
    category = await trait_category_factory(name="Thaumaturgy Paths Test")
    trait = await trait_factory(name="Biothaumaturgy Test", category=category)

    # When the syncer runs against a one-entry fixture
    syncer = TraitPowerSyncer()
    syncer.fixture_entries = [
        {
            "trait": "Biothaumaturgy Test",
            "category": "Thaumaturgy Paths Test",
            "subcategory": None,
            "powers": [
                {"level": 1, "name": "First", "description": "d", "system": "s", "link": None},
                {"level": 2, "name": "Second", "description": "d", "system": "s", "link": None},
            ],
        }
    ]
    await syncer.sync_entries()

    # Then two ordered powers exist for the trait
    powers = await TraitPower.filter(trait_id=trait.id).order_by("level")
    assert [p.name for p in powers] == ["First", "Second"]

    # cleanup (constant table)
    await TraitPower.filter(trait_id=trait.id).delete()


async def test_syncer_is_idempotent(trait_category_factory, trait_factory):
    """Verify re-running the syncer updates in place rather than duplicating."""
    # Given a trait and one fixture entry
    category = await trait_category_factory(name="Thaumaturgy Paths Idempotent")
    trait = await trait_factory(name="Biothaumaturgy Idempotent", category=category)
    entry = {
        "trait": "Biothaumaturgy Idempotent",
        "category": "Thaumaturgy Paths Idempotent",
        "subcategory": None,
        "powers": [{"level": 1, "name": "First", "description": "d", "system": None, "link": None}],
    }

    # When the syncer runs twice, the second time with a changed name
    s1 = TraitPowerSyncer()
    s1.fixture_entries = [entry]
    await s1.sync_entries()

    entry["powers"][0]["name"] = "First Renamed"
    s2 = TraitPowerSyncer()
    s2.fixture_entries = [entry]
    await s2.sync_entries()

    # Then there is still exactly one power, updated in place
    powers = await TraitPower.filter(trait_id=trait.id)
    assert len(powers) == 1
    assert powers[0].name == "First Renamed"

    await TraitPower.filter(trait_id=trait.id).delete()


async def test_syncer_raises_on_unresolved_trait():
    """Verify an entry referencing a missing trait raises rather than silently skipping."""
    # Given a fixture entry for a trait that does not exist
    syncer = TraitPowerSyncer()
    syncer.fixture_entries = [
        {"trait": "Nonexistent", "category": "Nope", "subcategory": None, "powers": []}
    ]

    # When the syncer runs, Then it raises
    with pytest.raises(ValueError, match="Nonexistent"):
        await syncer.sync_entries()


async def test_syncer_raises_on_ambiguous_trait(trait_category_factory, trait_factory):
    """Verify an entry matching more than one trait raises rather than picking arbitrarily."""
    # Given two traits sharing the same name under the same category
    category = await trait_category_factory(name="Thaumaturgy Paths Ambiguous")
    await trait_factory(name="Biothaumaturgy Ambiguous", category=category)
    await trait_factory(name="Biothaumaturgy Ambiguous", category=category)

    # When the syncer runs against an entry resolving to both traits
    syncer = TraitPowerSyncer()
    syncer.fixture_entries = [
        {
            "trait": "Biothaumaturgy Ambiguous",
            "category": "Thaumaturgy Paths Ambiguous",
            "subcategory": None,
            "powers": [
                {"level": 1, "name": "First", "description": "d", "system": None, "link": None}
            ],
        }
    ]

    # Then it raises, naming the ambiguous trait
    with pytest.raises(ValueError, match="Biothaumaturgy Ambiguous"):
        await syncer.sync_entries()
