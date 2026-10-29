"""Integration test for building a fresh schema the way `app migrate` and populate do."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from tortoise.context import TortoiseContext
from tortoise.migrations.loader import MigrationLoader
from tortoise.migrations.recorder import MigrationRecorder

from tests.services import PostgresService, admin_connection
from vapi.cli.migrate import build_fresh_schema
from vapi.db.sql_models.character_sheet import Trait
from vapi.lib.database import tortoise_config

pytestmark = pytest.mark.anyio


@pytest.fixture
async def empty_database_config(
    postgres_service: PostgresService,
) -> AsyncGenerator[dict]:
    """Create a throwaway empty database and yield a Tortoise config pointing at it."""
    name = f"vapi_fresh_{uuid.uuid4().hex[:12]}"
    admin = await admin_connection(postgres_service)
    await admin.execute(f'CREATE DATABASE "{name}"')
    await admin.close()
    config = tortoise_config()
    config["connections"]["default"]["credentials"]["database"] = name

    yield config

    admin = await admin_connection(postgres_service)
    await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    await admin.close()


async def test_build_fresh_schema_records_every_migration(empty_database_config: dict) -> None:
    """Verify every migration on disk is recorded as applied, so `migrate` replays none."""
    # Given an empty database in a context isolated from the session's Tortoise state
    async with TortoiseContext() as ctx:
        await ctx.init(config=empty_database_config)

        # When
        await build_fresh_schema(empty_database_config)
        recorder = MigrationRecorder(ctx.db("default"))
        applied = {(key.app_label, key.name) for key in await recorder.applied_migrations()}
        loader = MigrationLoader(empty_database_config["apps"], recorder)
        loader.load_disk()
        on_disk = {(key.app_label, key.name) for key in loader.disk_migrations}

    # Then
    assert on_disk
    assert applied == on_disk
    # The session database is still usable after the isolated context closes
    assert await Trait.all().count() > 0
