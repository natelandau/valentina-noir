"""Test that the migrate command leaves reference data seeded."""

import importlib

import pytest
from click.testing import CliRunner
from tortoise import Tortoise

from tests.fixtures import rolled_back_transaction
from vapi.cli.migrate import migrate
from vapi.cli.seed import seed_async
from vapi.constants import TrackerType
from vapi.db.sql_models.character_sheet import Trait

# `vapi.cli.migrate` resolves to the re-exported click command, not the module
migrate_module = importlib.import_module("vapi.cli.migrate")


def test_migrate_seeds_after_applying_migrations(mocker) -> None:
    """Verify `app migrate` runs the seed after applying migrations."""
    # Given the migration and seed steps are stubbed out
    steps = mocker.Mock()
    mocker.patch.object(migrate_module.asyncio, "run", new=steps.apply_migrations)
    mocker.patch.object(migrate_module, "run_with_tortoise", new=steps.seed)
    mocker.patch.object(migrate_module, "_apply_migrations", new=mocker.Mock())
    mocker.patch.object(migrate_module, "seed_async", new=mocker.Mock())

    # When the migrate command runs
    result = CliRunner().invoke(migrate)

    # Then migrations apply first, then the seed runs
    assert result.exit_code == 0, result.output
    assert [call[0] for call in steps.mock_calls] == ["apply_migrations", "seed"]


@pytest.mark.anyio
async def test_seed_fills_tracker_types_left_null_by_migration_0024() -> None:
    """Verify a database migrated through 0024 without seeding gets tracker types from the seed."""
    # Given tracker types are null, as migration 0024 leaves them
    # When the seed step of `app migrate` runs, inside a transaction rolled back to restore the traits
    found: dict[str, Trait] = {}
    async with rolled_back_transaction():
        await Tortoise.get_connection("default").execute_script(
            "UPDATE trait SET tracker_type_v4 = NULL, tracker_type_v5 = NULL;"
        )
        await seed_async()
        for name in ("Willpower", "Humanity", "Blood Pool"):
            found[name] = await Trait.get(name=name, custom_for_character_id=None)

    # Then fixture tracker types are filled in
    assert found["Willpower"].tracker_type_v4 == TrackerType.COUNTER
    assert found["Willpower"].tracker_type_v5 == TrackerType.COUNTER
    assert found["Humanity"].tracker_type_v4 == TrackerType.COUNTER
    assert found["Humanity"].tracker_type_v5 == TrackerType.STAINS
    assert found["Blood Pool"].tracker_type_v4 == TrackerType.COUNTER
