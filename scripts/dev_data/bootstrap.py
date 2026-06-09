"""Destructive database reset for dev-data population. Never called from tests."""

from tortoise import Tortoise

from vapi.cli.seed import seed_async
from vapi.lib.database import (
    drop_and_recreate_database,
    init_tortoise,
    install_archive_stamp_trigger,
)


async def reset_database() -> None:
    """Drop and recreate the database, build the schema, install triggers, and seed.

    Mirrors a migrated production database: generate_schemas skips migration RunSQL, so
    the archive-stamp trigger is installed explicitly. Leaves Tortoise initialized.
    """
    await drop_and_recreate_database()
    await init_tortoise()
    await Tortoise.generate_schemas(safe=True)
    await install_archive_stamp_trigger()
    await seed_async()
