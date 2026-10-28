"""Test the typed-damage to single-damage data migration in 0028."""

import importlib

import pytest
from tortoise.backends.base.client import BaseDBAsyncClient

from tests.fixtures import global_trait, rolled_back_transaction
from vapi.constants import CharacterClass, GameVersion
from vapi.db.sql_models.character import CharacterHealth, CharacterTrait

pytestmark = pytest.mark.anyio

migration = importlib.import_module("vapi.db.migrations.0028_simplify_trackers")

# Recreate the columns 0028 drops, inside the test transaction, so its SQL has data to read.
_RESTORE_LEGACY_COLUMNS_SQL = (
    "ALTER TABLE character_health"
    " ADD COLUMN bashing INT NOT NULL DEFAULT 0,"
    " ADD COLUMN lethal INT NOT NULL DEFAULT 0,"
    " ADD COLUMN superficial INT NOT NULL DEFAULT 0,"
    " ADD COLUMN aggravated INT NOT NULL DEFAULT 0;"
    "ALTER TABLE character_trait"
    " ADD COLUMN tracker_superficial INT NOT NULL DEFAULT 0,"
    " ADD COLUMN tracker_aggravated INT NOT NULL DEFAULT 0;"
)


async def _run_migration(conn: BaseDBAsyncClient) -> None:
    for sql in (
        migration.BACKFILL_HEALTH_DAMAGE_SQL,
        migration.BACKFILL_V5_WILLPOWER_SPENT_SQL,
        migration.CLEAR_NON_VAMPIRE_STAINS_SQL,
    ):
        await conn.execute_script(sql)


@pytest.mark.parametrize(
    ("size", "marks", "expected"),
    [
        (7, {"bashing": 2, "lethal": 1, "aggravated": 1}, 4),
        (6, {"superficial": 5, "aggravated": 3}, 6),
        (6, {}, 0),
    ],
    ids=["v4_typed_marks", "capped_at_size", "no_marks"],
)
async def test_health_marks_sum_into_damage(
    character_factory, character_health_factory, size, marks, expected
) -> None:
    """Verify every typed health mark becomes one point of damage, capped at the track size."""
    # Given a health row with typed marks under the old schema
    character = await character_factory(health=False)
    health = await character_health_factory(character=character, size=size)

    # When the migration SQL runs, inside a transaction rolled back to restore the schema
    damage = None
    async with rolled_back_transaction() as conn:
        await conn.execute_script(_RESTORE_LEGACY_COLUMNS_SQL)
        if marks:
            assignments = ", ".join(f"{column} = {value}" for column, value in marks.items())
            await conn.execute_query(
                f"UPDATE character_health SET {assignments} WHERE id = $1",  # noqa: S608
                [str(health.id)],
            )
        await _run_migration(conn)
        damage = (await CharacterHealth.get(id=health.id).using_db(conn)).damage

    # Then damage is the capped sum of the marks
    assert damage == expected


@pytest.mark.parametrize(
    ("game_version", "value", "superficial", "aggravated", "expected_spent"),
    [
        (GameVersion.V5, 4, 2, 1, 3),
        (GameVersion.V5, 2, 2, 2, 2),
        (GameVersion.V4, 5, 2, 1, 0),
    ],
    ids=["v5_damage_becomes_spent", "v5_capped_at_value", "v4_untouched"],
)
async def test_v5_willpower_damage_becomes_spent(
    character_factory,
    character_trait_factory,
    game_version,
    value,
    superficial,
    aggravated,
    expected_spent,
) -> None:
    """Verify V5 Willpower damage becomes spent points and V4 Willpower is left alone."""
    # Given a Willpower row with damage marks under the old schema
    character = await character_factory(game_version=game_version)
    willpower = await character_trait_factory(
        character=character, trait=await global_trait("Willpower"), value=value
    )

    # When the migration SQL runs, inside a transaction rolled back to restore the schema
    spent = None
    async with rolled_back_transaction() as conn:
        await conn.execute_script(_RESTORE_LEGACY_COLUMNS_SQL)
        await conn.execute_query(
            "UPDATE character_trait SET tracker_superficial = $1, tracker_aggravated = $2"
            " WHERE id = $3",
            [superficial, aggravated, str(willpower.id)],
        )
        await _run_migration(conn)
        spent = (await CharacterTrait.get(id=willpower.id).using_db(conn)).tracker_spent

    # Then spent follows the damage only for V5
    assert spent == expected_spent


@pytest.mark.parametrize(
    ("game_version", "character_class", "expected_stains"),
    [
        (GameVersion.V5, CharacterClass.VAMPIRE, 3),
        (GameVersion.V5, CharacterClass.MORTAL, 0),
        (GameVersion.V5, CharacterClass.HUNTER, 0),
        (GameVersion.V4, CharacterClass.VAMPIRE, 0),
    ],
)
async def test_stains_kept_only_for_v5_vampires(
    character_factory, character_trait_factory, game_version, character_class, expected_stains
) -> None:
    """Verify only V5 vampires keep their stains."""
    # Given a Humanity row with 3 stains
    character = await character_factory(game_version=game_version, character_class=character_class)
    humanity = await character_trait_factory(
        character=character, trait=await global_trait("Humanity"), value=7, tracker_stains=3
    )

    # When the migration SQL runs, inside a transaction rolled back to restore the schema
    stains = None
    async with rolled_back_transaction() as conn:
        await conn.execute_script(_RESTORE_LEGACY_COLUMNS_SQL)
        await _run_migration(conn)
        stains = (await CharacterTrait.get(id=humanity.id).using_db(conn)).tracker_stains

    # Then stains survive only for a V5 vampire
    assert stains == expected_stains
