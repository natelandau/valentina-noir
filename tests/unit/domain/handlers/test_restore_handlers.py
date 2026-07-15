"""Tests for batch restore."""

import pytest

from vapi.db.sql_models.base import new_uuid
from vapi.db.sql_models.character import Character, Specialty
from vapi.db.sql_models.character_sheet import Trait, TraitPower
from vapi.domain.handlers import archive_character, restore_archive_batch

pytestmark = pytest.mark.anyio


async def test_restore_unknown_batch_returns_zero() -> None:
    """Verify restoring a batch id that matches no rows returns zero."""
    # Given a batch id that was never used
    unused_batch_id = new_uuid()

    # When that batch is restored
    restored = await restore_archive_batch(batch_id=unused_batch_id)

    # Then no rows are touched
    assert restored == 0


async def test_restore_batch_reactivates_whole_action(
    company_factory,
    user_factory,
    character_factory,
    specialty_factory,
) -> None:
    """Verify restoring a batch reactivates every row that action archived."""
    # Given an archived character with a child, captured batch id
    company = await company_factory()
    user = await user_factory(company=company)
    character = await character_factory(company=company, user_player=user, user_creator=user)
    specialty = await specialty_factory(character=character)
    ctx = await archive_character(character=character)

    # When the batch is restored
    restored = await restore_archive_batch(batch_id=ctx.batch_id)

    # Then every row is active again with cleared stamps
    assert restored >= 2
    for obj, model in [(character, Character), (specialty, Specialty)]:
        refreshed = await model.get(id=obj.id)
        assert refreshed.is_archived is False
        assert refreshed.archive_date is None
        assert refreshed.archive_batch_id is None


async def test_restore_reactivates_custom_traits_and_their_powers(
    character_factory,
    trait_factory,
    trait_power_factory,
) -> None:
    """Verify unarchiving a character brings its custom traits and their powers back."""
    # Given an archived character whose custom trait grants a power
    character = await character_factory()
    custom_trait = await trait_factory(custom_for_character_id=character.id)
    power = await trait_power_factory(trait=custom_trait, level=1, name="Custom Power")
    ctx = await archive_character(character=character)
    assert (await Trait.get(id=custom_trait.id)).is_archived
    assert (await TraitPower.get(id=power.id)).is_archived

    # When the character is restored
    await restore_archive_batch(batch_id=ctx.batch_id)

    # Then the trait and its power are active again
    for obj, model in [(custom_trait, Trait), (power, TraitPower)]:
        refreshed = await model.get(id=obj.id)
        assert refreshed.is_archived is False
        assert refreshed.archive_batch_id is None


async def test_restore_leaves_independently_archived_rows_alone(
    company_factory,
    user_factory,
    character_factory,
    specialty_factory,
) -> None:
    """Verify restore does not reactivate a child archived under a different batch."""
    # Given a specialty archived on its own (batch A), then its character archived (batch B)
    company = await company_factory()
    user = await user_factory(company=company)
    character = await character_factory(company=company, user_player=user, user_creator=user)
    specialty = await specialty_factory(character=character)
    specialty.is_archived = True
    await specialty.save()  # batch A
    batch_a = (await Specialty.get(id=specialty.id)).archive_batch_id
    ctx = await archive_character(character=character)  # batch B (skips already-archived specialty)

    # When batch B is restored
    await restore_archive_batch(batch_id=ctx.batch_id)

    # Then the character is active but the independently-archived specialty stays archived
    assert (await Character.get(id=character.id)).is_archived is False
    refreshed_specialty = await Specialty.get(id=specialty.id)
    assert refreshed_specialty.is_archived is True
    assert refreshed_specialty.archive_batch_id == batch_a
