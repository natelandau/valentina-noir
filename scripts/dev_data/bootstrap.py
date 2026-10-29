"""Destructive database reset for dev-data population. Never called from tests."""

from vapi.cli.migrate import build_fresh_schema
from vapi.cli.seed import seed_async
from vapi.lib.database import drop_and_recreate_database, init_tortoise, tortoise_config


async def reset_database() -> None:
    """Drop and recreate the database, build the schema as `app migrate` would, and seed.

    Every migration is recorded as applied, so a later `app migrate` only runs newer ones.
    Leaves Tortoise initialized.
    """
    await drop_and_recreate_database()
    await init_tortoise()
    await build_fresh_schema(tortoise_config())
    await seed_async()
