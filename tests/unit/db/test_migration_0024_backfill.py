"""Test the health and V5 Willpower data backfill in migration 0024."""

import importlib
from uuid import uuid4

import pytest
from tortoise import Tortoise
from tortoise.transactions import in_transaction

from vapi.db.sql_models.character import CharacterHealth, CharacterTrait
from vapi.db.sql_models.character_sheet import Trait

pytestmark = pytest.mark.anyio

migration = importlib.import_module("vapi.db.migrations.0024_auto_20261023_2254")


class _Rollback(Exception):  # noqa: N818
    """Raised to roll back a transaction on purpose."""


async def _run(sql: str) -> None:
    await Tortoise.get_connection("default").execute_script(sql)


async def _run_backfill() -> None:
    await _run(migration.BACKFILL_HEALTH_SQL)
    await _run(migration.BACKFILL_V5_WILLPOWER_SQL)


async def _global_trait(name: str) -> Trait:
    return await Trait.get(name=name, custom_for_character_id=None)


async def _willpower_rows(character_id) -> list[CharacterTrait]:
    return await CharacterTrait.filter(
        character_id=character_id,
        trait__name="Willpower",
        trait__custom_for_character_id__isnull=True,
    ).all()


async def test_backfill_creates_v5_health_sized_from_stamina(
    character_factory, character_trait_factory
) -> None:
    """Verify a V5 character without health gets a track of Stamina + 3 with no marks."""
    # Given a V5 character with Stamina 3 and no health row
    character = await character_factory(game_version="V5", health=False)
    await character_trait_factory(
        character=character, trait=await _global_trait("Stamina"), value=3
    )

    # When the health backfill runs
    await _run(migration.BACKFILL_HEALTH_SQL)

    # Then one empty health row of size 6 exists
    health = await CharacterHealth.filter(character_id=character.id).all()
    assert len(health) == 1
    assert health[0].size == 6
    assert health[0].extra_levels == 0
    assert (health[0].bashing, health[0].lethal) == (0, 0)
    assert (health[0].superficial, health[0].aggravated) == (0, 0)
    assert health[0].is_archived is False
    assert health[0].archive_date is None
    assert health[0].archive_batch_id is None


async def test_backfill_creates_v5_health_without_stamina(character_factory) -> None:
    """Verify a V5 character with no Stamina trait counts Stamina as 0."""
    # Given a V5 character with no traits and no health row
    character = await character_factory(game_version="V5", health=False)

    # When the health backfill runs
    await _run(migration.BACKFILL_HEALTH_SQL)

    # Then the health size is the V5 base of 3
    health = await CharacterHealth.get(character_id=character.id)
    assert health.size == 3


async def test_backfill_creates_v4_health_size_seven(
    character_factory, character_trait_factory
) -> None:
    """Verify a V4 character gets the fixed seven-level track regardless of Stamina."""
    # Given a V4 character with Stamina 4 and no health row
    character = await character_factory(game_version="V4", health=False)
    await character_trait_factory(
        character=character, trait=await _global_trait("Stamina"), value=4
    )

    # When the health backfill runs
    await _run(migration.BACKFILL_HEALTH_SQL)

    # Then the health size is 7
    health = await CharacterHealth.get(character_id=character.id)
    assert health.size == 7
    assert health.extra_levels == 0


async def test_backfill_keeps_existing_health(character_factory) -> None:
    """Verify a character that already has a health row is left alone."""
    # Given a V5 character whose health row has damage marked
    character = await character_factory(game_version="V5")
    await CharacterHealth.filter(character_id=character.id).update(size=9, superficial=2)

    # When the health backfill runs
    await _run(migration.BACKFILL_HEALTH_SQL)

    # Then the existing row is unchanged and no second row exists
    health = await CharacterHealth.filter(character_id=character.id).all()
    assert len(health) == 1
    assert health[0].size == 9
    assert health[0].superficial == 2


async def test_backfill_copies_archive_state(character_factory, character_trait_factory) -> None:
    """Verify an archived character's health is archived with it and sized from its archived Stamina."""
    # Given an archived V5 character whose Stamina 4 was archived with it,
    # plus a stray live Stamina row that must be ignored
    character = await character_factory(game_version="V5", health=False, is_archived=True)
    stamina = await _global_trait("Stamina")
    await character_trait_factory(
        character=character,
        trait=stamina,
        value=4,
        is_archived=True,
        archive_date=character.archive_date,
        archive_batch_id=character.archive_batch_id,
    )
    await character_trait_factory(character=character, trait=stamina, value=1)

    # When the health backfill runs
    await _run(migration.BACKFILL_HEALTH_SQL)

    # Then the health row carries the character's archive stamps and size 7
    health = await CharacterHealth.get(character_id=character.id)
    assert health.is_archived is True
    assert health.archive_date == character.archive_date
    assert health.archive_batch_id == character.archive_batch_id
    assert health.size == 7


async def test_backfill_adds_missing_v5_willpower(
    character_factory, character_trait_factory
) -> None:
    """Verify a V5 character without Willpower gets Composure + Resolve with an empty track."""
    # Given a V5 character with Composure 2 and Resolve 3 but no Willpower
    character = await character_factory(game_version="V5")
    await character_trait_factory(
        character=character, trait=await _global_trait("Composure"), value=2
    )
    await character_trait_factory(
        character=character, trait=await _global_trait("Resolve"), value=3
    )

    # When the Willpower backfill runs
    await _run(migration.BACKFILL_V5_WILLPOWER_SQL)

    # Then one live Willpower row of value 5 with no marks exists
    rows = await _willpower_rows(character.id)
    assert len(rows) == 1
    assert rows[0].value == 5
    assert rows[0].tracker_superficial == 0
    assert rows[0].tracker_aggravated == 0
    assert rows[0].tracker_spent == 0
    assert rows[0].tracker_stains == 0
    assert rows[0].is_archived is False
    assert rows[0].archive_batch_id is None


async def test_backfill_counts_missing_attribute_as_zero(
    character_factory, character_trait_factory
) -> None:
    """Verify a missing attribute, or one archived apart from a live character, counts as 0."""
    # Given a live V5 character with Composure 2 and only an archived Resolve row
    character = await character_factory(game_version="V5")
    await character_trait_factory(
        character=character, trait=await _global_trait("Composure"), value=2
    )
    await character_trait_factory(
        character=character, trait=await _global_trait("Resolve"), value=4, is_archived=True
    )

    # When the Willpower backfill runs
    await _run(migration.BACKFILL_V5_WILLPOWER_SQL)

    # Then Willpower is 2
    rows = await _willpower_rows(character.id)
    assert len(rows) == 1
    assert rows[0].value == 2
    assert rows[0].is_archived is False


async def test_backfill_adds_willpower_to_archived_v5_character(
    character_factory, character_trait_factory
) -> None:
    """Verify an archived V5 character gets Willpower archived with it from its archived attributes."""
    # Given an archived V5 character whose Composure 3 and Resolve 1 were archived with it
    character = await character_factory(game_version="V5", is_archived=True)
    for name, value in (("Composure", 3), ("Resolve", 1)):
        await character_trait_factory(
            character=character,
            trait=await _global_trait(name),
            value=value,
            is_archived=True,
            archive_date=character.archive_date,
            archive_batch_id=character.archive_batch_id,
        )

    # When the Willpower backfill runs
    await _run(migration.BACKFILL_V5_WILLPOWER_SQL)

    # Then one archived Willpower row of value 4 shares the character's archive stamps
    rows = await _willpower_rows(character.id)
    assert len(rows) == 1
    assert rows[0].value == 4
    assert rows[0].is_archived is True
    assert rows[0].archive_date == character.archive_date
    assert rows[0].archive_batch_id == character.archive_batch_id


async def test_backfill_corrects_wrong_v5_willpower(
    character_factory, character_trait_factory
) -> None:
    """Verify an existing V5 Willpower that differs from Composure + Resolve is corrected."""
    # Given a V5 character with Composure 3, Resolve 3 and Willpower 2
    character = await character_factory(game_version="V5")
    await character_trait_factory(
        character=character, trait=await _global_trait("Composure"), value=3
    )
    await character_trait_factory(
        character=character, trait=await _global_trait("Resolve"), value=3
    )
    willpower = await character_trait_factory(
        character=character, trait=await _global_trait("Willpower"), value=2
    )

    # When the Willpower backfill runs
    await _run(migration.BACKFILL_V5_WILLPOWER_SQL)

    # Then the same row now holds 6 and no other Willpower row exists
    rows = await _willpower_rows(character.id)
    assert [row.id for row in rows] == [willpower.id]
    assert rows[0].value == 6


async def test_backfill_trims_superficial_first_when_lowering_willpower(
    character_factory, character_trait_factory
) -> None:
    """Verify lowering Willpower trims superficial marks before aggravated ones."""
    # Given a V5 Willpower of 7 with 3 superficial and 3 aggravated marks that should be 4
    character = await character_factory(game_version="V5")
    await character_trait_factory(
        character=character, trait=await _global_trait("Composure"), value=2
    )
    await character_trait_factory(
        character=character, trait=await _global_trait("Resolve"), value=2
    )
    willpower = await character_trait_factory(
        character=character,
        trait=await _global_trait("Willpower"),
        value=7,
        tracker_superficial=3,
        tracker_aggravated=3,
    )

    # When the Willpower backfill runs
    await _run(migration.BACKFILL_V5_WILLPOWER_SQL)

    # Then two superficial marks are trimmed so the marks fit the new value
    row = await CharacterTrait.get(id=willpower.id)
    assert row.value == 4
    assert row.tracker_superficial == 1
    assert row.tracker_aggravated == 3


async def test_backfill_trims_aggravated_after_superficial_runs_out(
    character_factory, character_trait_factory
) -> None:
    """Verify aggravated marks are trimmed once no superficial marks remain."""
    # Given a V5 Willpower of 7 with 1 superficial and 5 aggravated marks that should be 3
    character = await character_factory(game_version="V5")
    await character_trait_factory(
        character=character, trait=await _global_trait("Composure"), value=1
    )
    await character_trait_factory(
        character=character, trait=await _global_trait("Resolve"), value=2
    )
    willpower = await character_trait_factory(
        character=character,
        trait=await _global_trait("Willpower"),
        value=7,
        tracker_superficial=1,
        tracker_aggravated=5,
    )

    # When the Willpower backfill runs
    await _run(migration.BACKFILL_V5_WILLPOWER_SQL)

    # Then the superficial mark and two aggravated marks are trimmed
    row = await CharacterTrait.get(id=willpower.id)
    assert row.value == 3
    assert row.tracker_superficial == 0
    assert row.tracker_aggravated == 3


async def test_backfill_skips_v4_willpower(character_factory, character_trait_factory) -> None:
    """Verify V4 characters get no Willpower and keep the Willpower they have."""
    # Given a V4 character without Willpower and a V4 character with Willpower 9,
    # both with Composure 2 and Resolve 2
    composure = await _global_trait("Composure")
    resolve = await _global_trait("Resolve")
    without = await character_factory(game_version="V4")
    with_willpower = await character_factory(game_version="V4")
    for character in (without, with_willpower):
        await character_trait_factory(character=character, trait=composure, value=2)
        await character_trait_factory(character=character, trait=resolve, value=2)
    existing = await character_trait_factory(
        character=with_willpower, trait=await _global_trait("Willpower"), value=9
    )

    # When the Willpower backfill runs
    await _run(migration.BACKFILL_V5_WILLPOWER_SQL)

    # Then neither V4 character is changed
    assert await _willpower_rows(without.id) == []
    rows = await _willpower_rows(with_willpower.id)
    assert [row.id for row in rows] == [existing.id]
    assert rows[0].value == 9


async def test_backfill_is_idempotent(character_factory, character_trait_factory) -> None:
    """Verify running the backfill twice creates no duplicate rows."""
    # Given a V5 character with Composure 2, Resolve 2, Stamina 2 and neither health nor Willpower
    character = await character_factory(game_version="V5", health=False)
    for name in ("Composure", "Resolve", "Stamina"):
        await character_trait_factory(character=character, trait=await _global_trait(name), value=2)

    # When both backfill statements run twice
    await _run_backfill()
    await _run_backfill()

    # Then exactly one health row and one Willpower row exist
    health = await CharacterHealth.filter(character_id=character.id).all()
    assert len(health) == 1
    assert health[0].size == 5
    rows = await _willpower_rows(character.id)
    assert len(rows) == 1
    assert rows[0].value == 4


async def test_backfill_does_nothing_without_willpower_trait(
    character_factory, character_trait_factory
) -> None:
    """Verify the Willpower backfill inserts nothing and does not fail before traits are seeded."""
    # Given a V5 character without Willpower in a database with no global Willpower trait
    character = await character_factory(game_version="V5")
    await character_trait_factory(
        character=character, trait=await _global_trait("Composure"), value=2
    )
    count_before = await CharacterTrait.all().count()

    # When the Willpower backfill runs, inside a transaction rolled back to restore the trait
    count_after = None
    try:
        async with in_transaction() as conn:
            await (
                Trait.filter(name="Willpower", custom_for_character_id__isnull=True)
                .using_db(conn)
                .update(name="Willpower (hidden)")
            )
            await conn.execute_script(migration.BACKFILL_V5_WILLPOWER_SQL)
            count_after = await CharacterTrait.all().using_db(conn).count()
            raise _Rollback  # noqa: TRY301
    except _Rollback:
        pass

    # Then no character trait was added
    assert count_after == count_before


async def test_backfill_ignores_willpower_from_another_archive_batch(
    character_factory, character_trait_factory
) -> None:
    """Verify an archived character reads and writes only rows in its own archive batch."""
    # Given an archived V5 character with Composure 2 in its own batch, and a Resolve 5
    # and Willpower 9 archived earlier in a different batch
    character = await character_factory(game_version="V5", is_archived=True)
    await character_trait_factory(
        character=character,
        trait=await _global_trait("Composure"),
        value=2,
        is_archived=True,
        archive_date=character.archive_date,
        archive_batch_id=character.archive_batch_id,
    )
    other_batch = {"is_archived": True, "archive_batch_id": uuid4()}
    await character_trait_factory(
        character=character, trait=await _global_trait("Resolve"), value=5, **other_batch
    )
    stale = await character_trait_factory(
        character=character, trait=await _global_trait("Willpower"), value=9, **other_batch
    )

    # When the Willpower backfill runs
    await _run(migration.BACKFILL_V5_WILLPOWER_SQL)

    # Then a new Willpower of 2 is archived in the character's batch and the stale row is unchanged
    rows = await _willpower_rows(character.id)
    new_rows = [row for row in rows if row.id != stale.id]
    assert len(rows) == 2
    assert len(new_rows) == 1
    assert new_rows[0].value == 2
    assert new_rows[0].is_archived is True
    assert new_rows[0].archive_batch_id == character.archive_batch_id
    stale_after = next(row for row in rows if row.id == stale.id)
    assert stale_after.value == 9
    assert stale_after.archive_batch_id == stale.archive_batch_id


async def test_backfill_ignores_custom_traits_with_global_names(
    character_factory, character_trait_factory, trait_factory
) -> None:
    """Verify custom traits named Stamina or Willpower neither size health nor count as Willpower."""
    # Given a V5 character with global Stamina 2, Composure 1 and Resolve 1, plus custom
    # "Stamina" 5 and custom "Willpower" 8 traits, and no health row
    character = await character_factory(game_version="V5", health=False)
    for name in ("Stamina", "Composure", "Resolve"):
        value = 2 if name == "Stamina" else 1
        await character_trait_factory(
            character=character, trait=await _global_trait(name), value=value
        )
    custom_stamina = await trait_factory(name="Stamina", custom_for_character_id=character.id)
    custom_willpower = await trait_factory(name="Willpower", custom_for_character_id=character.id)
    await character_trait_factory(character=character, trait=custom_stamina, value=5)
    custom_row = await character_trait_factory(character=character, trait=custom_willpower, value=8)

    # When both backfill statements run
    await _run_backfill()

    # Then health is sized from the global Stamina, a global Willpower of 2 is added,
    # and the custom Willpower row is unchanged
    health = await CharacterHealth.get(character_id=character.id)
    assert health.size == 5
    rows = await _willpower_rows(character.id)
    assert len(rows) == 1
    assert rows[0].value == 2
    assert (await CharacterTrait.get(id=custom_row.id)).value == 8


async def test_backfill_handles_duplicate_live_attribute_rows(
    character_factory, character_trait_factory
) -> None:
    """Verify two live Composure rows yield one Willpower from the most recent row, without error."""
    # Given a V5 character with Composure rows of 2 then 3 and Resolve 1
    character = await character_factory(game_version="V5")
    composure = await _global_trait("Composure")
    await character_trait_factory(character=character, trait=composure, value=2)
    await character_trait_factory(character=character, trait=composure, value=3)
    await character_trait_factory(
        character=character, trait=await _global_trait("Resolve"), value=1
    )

    # When the Willpower backfill runs
    await _run(migration.BACKFILL_V5_WILLPOWER_SQL)

    # Then one Willpower row holds the latest Composure plus Resolve
    rows = await _willpower_rows(character.id)
    assert len(rows) == 1
    assert rows[0].value == 4
