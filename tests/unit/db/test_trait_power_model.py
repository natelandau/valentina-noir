"""Unit tests for the TraitPower model."""

import pytest
from tortoise.exceptions import IntegrityError

from vapi.db.sql_models.character_sheet import Trait, TraitPower


@pytest.mark.anyio
async def test_trait_power_created_with_level(trait_factory, trait_power_factory):
    """Verify a TraitPower persists with its trait, level, and text fields."""
    # Given a trait
    trait = await trait_factory(name="Biothaumaturgy")

    # When a power is created at level 1
    power = await trait_power_factory(
        trait=trait,
        level=1,
        name="Thaumaturgical Forensics",
        description="Read the history of a corpse.",
        system="Roll Perception + Medicine.",
    )

    # Then it is stored against the trait at that level
    assert power.level == 1
    assert power.name == "Thaumaturgical Forensics"
    # str() sidesteps uuid_utils.UUID (in-memory default) vs uuid.UUID (DB round trip)
    # comparing unequal despite matching values.
    assert str((await TraitPower.get(id=power.id)).trait_id) == str(trait.id)


@pytest.mark.anyio
async def test_trait_power_unique_per_level(trait_factory, trait_power_factory):
    """Verify two powers cannot share the same (trait, level)."""
    # Given a trait with a level-1 power
    trait = await trait_factory(name="Biothaumaturgy")
    await trait_power_factory(trait=trait, level=1, name="First")

    # When a second level-1 power is added, Then it raises
    with pytest.raises(IntegrityError):
        await trait_power_factory(trait=trait, level=1, name="Second")


@pytest.mark.anyio
async def test_trait_power_default_ordering_by_level(trait_factory, trait_power_factory):
    """Verify prefetched powers come back in ascending level order."""
    # Given a trait with powers inserted out of level order
    trait = await trait_factory(name="Biothaumaturgy")
    await trait_power_factory(trait=trait, level=2, name="Second")
    await trait_power_factory(trait=trait, level=1, name="First")

    # When the trait's powers are fetched
    # Re-fetch first: fetch_related on the in-memory instance would key its
    # reverse-relation lookup on the uuid_utils.UUID default id, which never
    # matches the uuid.UUID a DB round trip parses trait_id into.
    trait = await Trait.get(id=trait.id)
    await trait.fetch_related("powers")

    # Then they are ordered by level ascending
    assert [p.level for p in trait.powers] == [1, 2]


@pytest.mark.anyio
async def test_trait_power_cascades_on_trait_delete(trait_factory, trait_power_factory):
    """Verify deleting a trait removes its powers."""
    # Given a trait with a power
    trait = await trait_factory(name="Biothaumaturgy")
    power = await trait_power_factory(trait=trait, level=1, name="First")

    # When the trait is deleted
    await trait.delete()

    # Then the power is gone
    assert await TraitPower.filter(id=power.id).first() is None
