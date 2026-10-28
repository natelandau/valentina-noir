"""Test the duplicate nameless trait power cleanup in migration 0025."""

import importlib

import pytest

from tests.fixtures import rolled_back_transaction
from vapi.db.sql_models.character_sheet import TraitPower

pytestmark = pytest.mark.anyio

migration = importlib.import_module("vapi.db.migrations.0025_trait_power_nameless_unique")


async def test_dedupe_keeps_active_descriptor_over_older_archived_one(
    trait_factory, trait_power_factory
) -> None:
    """Verify the cleanup keeps the active nameless descriptor when an older one is archived."""
    # Given a trait
    trait = await trait_factory()

    # When an archived and a newer active nameless descriptor share a level and the
    # cleanup runs, inside a transaction rolled back to restore the unique index
    remaining_ids = None
    active_id = None
    async with rolled_back_transaction() as conn:
        await conn.execute_script("DROP INDEX IF EXISTS uidx_trait_power_nameless_level;")
        await trait_power_factory(trait=trait, level=1, name=None, is_archived=True)
        active = await trait_power_factory(trait=trait, level=1, name=None)
        active_id = active.id
        await conn.execute_script(migration.DEDUPE_NAMELESS_SQL)
        remaining_ids = await (
            TraitPower.filter(trait_id=trait.id, level=1, name__isnull=True)
            .using_db(conn)
            .values_list("id", flat=True)
        )

    # Then only the active descriptor remains
    assert remaining_ids == [active_id]
