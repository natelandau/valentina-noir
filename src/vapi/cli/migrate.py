"""Migration CLI: apply and generate database migrations."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import Any

import click
from tortoise.migrations.api import migrate as tortoise_migrate
from tortoise.migrations.loader import MigrationLoader
from tortoise.migrations.recorder import MigrationRecorder

from vapi.cli.lib.runner import run_with_tortoise
from vapi.cli.seed import seed_async
from vapi.lib.database import install_schema_extras, tortoise_config

logger = logging.getLogger("vapi")


async def _apply_migrations() -> None:
    """Apply all pending migrations.

    Use ``generate_schemas`` for initial setup because Tortoise ORM's migration
    ``CreateModel`` operation silently drops foreign-key columns. Once the
    schema exists, subsequent migrations work correctly.
    """
    from tortoise import Tortoise

    config = tortoise_config()
    await Tortoise.init(config=config)

    # Let probe failures (bad connection, permissions) surface rather than
    # misclassifying a reachable-but-broken database as fresh and re-bootstrapping it.
    conn = Tortoise.get_connection("default")
    _, rows = await conn.execute_query(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'trait')"
    )
    tables_exist = rows[0]["exists"]

    if tables_exist:
        await Tortoise.close_connections()
        await tortoise_migrate(config=config)
        return

    await build_fresh_schema(config)
    await Tortoise.close_connections()


async def build_fresh_schema(config: dict[str, Any]) -> None:
    """Build an empty database's schema from the models and mark every migration applied.

    Use this instead of ``generate_schemas`` alone on an empty database, so a later
    ``migrate`` does not replay migrations against tables that already exist. Tortoise must
    already be initialized.

    Args:
        config: The Tortoise config the migrations are loaded with.
    """
    from tortoise import Tortoise
    from tortoise.transactions import in_transaction

    # One transaction so a crash never leaves a populated schema without its markers, which
    # would make the next migrate run try to re-apply migrations against existing tables.
    async with in_transaction():
        await Tortoise.generate_schemas()
        # generate_schemas skips migration RunSQL; install the trigger and indexes it
        # cannot express so fresh databases get the same DB-level backstops as migrated ones.
        await install_schema_extras()
        tx_conn = Tortoise.get_connection("default")
        await tx_conn.execute_script(
            "CREATE TABLE IF NOT EXISTS tortoise_migrations ("
            "  id SERIAL PRIMARY KEY,"
            "  app VARCHAR(100) NOT NULL,"
            "  name VARCHAR(255) NOT NULL,"
            "  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
            ");"
        )
        # generate_schemas builds the schema from the current models, so a fresh
        # database already reflects every migration, not just 0001_initial. Record
        # them all, or the next migrate replays them against the schema they already
        # produced. Skipping the SQL they carry is safe for the same reason: a data
        # migration has no rows to touch here, schema SQL only restates what
        # generate_schemas already built, and the trigger and indexes it cannot
        # express are installed above.
        recorder = MigrationRecorder(tx_conn)
        loader = MigrationLoader(config["apps"], recorder)
        loader.load_disk()
        for key in loader.disk_migrations:
            await recorder.record_applied(key.app_label, key.name)


@click.command(
    name="migrate",
    help="Apply pending database migrations, then seed reference data.",
)
def migrate() -> None:
    """Apply all pending database migrations, then seed reference data.

    Migrations can add reference-data columns that only the seed fills in, so a migrated
    database is never correct until a seed runs. Seeding here makes that impossible to skip.
    """
    asyncio.run(_apply_migrations())
    click.echo("Migrations applied successfully.")
    run_with_tortoise(seed_async())
    click.echo("Reference data seeded successfully.")


@click.command(
    name="makemigrations",
    help="Generate migration files from model changes.",
)
@click.option("--name", "-n", default=None, help="Name for the migration file.")
def makemigrations(name: str | None) -> None:
    """Generate new migration files by detecting model changes."""
    cmd = [
        "tortoise",
        "-c",
        "vapi.lib.database.TORTOISE_ORM",
        "makemigrations",
    ]
    if name:
        cmd.extend(["--name", name])
    result = subprocess.run(cmd, check=False)  # noqa: S603
    raise SystemExit(result.returncode)
