"""Test that custom traits are owned by, and deleted with, their character."""

import uuid

import pytest
from tortoise.exceptions import IntegrityError

from vapi.db.sql_models.character_sheet import Trait, TraitPower

pytestmark = pytest.mark.anyio


async def test_deleting_character_deletes_its_custom_traits(
    character_factory, trait_factory
) -> None:
    """Verify a hard-deleted character takes its custom traits with it.

    Characters are hard-deleted outside the archive flow (expired chargen sessions,
    the temporary-character purge), so the DB cascade is the only thing standing
    between those paths and orphaned custom traits.
    """
    # Given a character with a custom trait
    character = await character_factory()
    custom_trait = await trait_factory(custom_for_character_id=character.id)

    # When the character is hard-deleted
    await character.delete()

    # Then the custom trait is gone too
    assert await Trait.filter(id=custom_trait.id).count() == 0


async def test_deleting_character_deletes_its_custom_trait_powers(
    character_factory, trait_factory, trait_power_factory
) -> None:
    """Verify the cascade reaches through a custom trait to its powers."""
    # Given a character with a custom trait that grants a power
    character = await character_factory()
    custom_trait = await trait_factory(custom_for_character_id=character.id)
    power = await trait_power_factory(trait=custom_trait, level=1, name="Custom Power")

    # When the character is hard-deleted
    await character.delete()

    # Then the trait's power is gone with it
    assert await TraitPower.filter(id=power.id).count() == 0


async def test_deleting_character_leaves_global_traits_intact(
    character_factory, trait_factory, trait_power_factory
) -> None:
    """Verify the cascade is scoped to custom traits and spares the seeded ones."""
    # Given a character, and a global trait owned by nobody
    character = await character_factory()
    global_trait = await trait_factory()
    global_power = await trait_power_factory(trait=global_trait, level=1, name="Global Power")

    # When the character is hard-deleted
    await character.delete()

    # Then the global trait and its power survive
    assert await Trait.filter(id=global_trait.id).count() == 1
    assert await TraitPower.filter(id=global_power.id).count() == 1


async def test_custom_trait_cannot_reference_a_missing_character(trait_factory) -> None:
    """Verify the owner column is a real FK, not a loose id."""
    # Given a character id that does not exist
    missing_character_id = uuid.uuid4()

    # When a custom trait claims that character as its owner
    # Then the database rejects it
    with pytest.raises(IntegrityError):
        await trait_factory(custom_for_character_id=missing_character_id)
