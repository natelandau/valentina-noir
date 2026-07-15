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
    assert (await TraitPower.get(id=power.id)).trait_id == trait.id


@pytest.mark.anyio
async def test_trait_power_multiple_per_level(trait_factory, trait_power_factory):
    """Verify a trait may grant multiple differently-named powers at one level."""
    # Given a trait (a Discipline offers several powers to choose from per dot)
    trait = await trait_factory(name="Auspex")

    # When two differently-named powers are added at level 1
    await trait_power_factory(trait=trait, level=1, name="Heightened Senses")
    await trait_power_factory(trait=trait, level=1, name="Sense the Unseen")

    # Then both persist against the trait at that level
    trait = await Trait.get(id=trait.id)
    await trait.fetch_related("powers")
    assert sorted(p.name for p in trait.powers) == ["Heightened Senses", "Sense the Unseen"]


@pytest.mark.anyio
async def test_trait_power_nameless_dot_descriptor(trait_factory, trait_power_factory):
    """Verify a trait may store a nameless per-dot descriptor with a null name."""
    # Given a trait whose dots carry only descriptive text (an Attribute or Skill)
    trait = await trait_factory(name="Firearms")

    # When a nameless power is created at level 1
    power = await trait_power_factory(
        trait=trait,
        level=1,
        name=None,
        description="They've fired a gun a few times.",
    )

    # Then it persists with a null name
    stored = await TraitPower.get(id=power.id)
    assert stored.name is None
    assert stored.description == "They've fired a gun a few times."


@pytest.mark.anyio
async def test_trait_power_unique_per_level_and_name(trait_factory, trait_power_factory):
    """Verify the same power cannot be seeded twice at the same (trait, level, name)."""
    # Given a trait with a level-1 power
    trait = await trait_factory(name="Auspex")
    await trait_power_factory(trait=trait, level=1, name="Heightened Senses")

    # When an identically-named power is added at the same level, Then it raises
    with pytest.raises(IntegrityError):
        await trait_power_factory(trait=trait, level=1, name="Heightened Senses")


@pytest.mark.anyio
async def test_trait_power_default_ordering_by_level(trait_factory, trait_power_factory):
    """Verify prefetched powers come back in ascending level order."""
    # Given a trait with powers inserted out of level order
    trait = await trait_factory(name="Biothaumaturgy")
    await trait_power_factory(trait=trait, level=2, name="Second")
    await trait_power_factory(trait=trait, level=1, name="First")

    # When the trait's powers are fetched
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
