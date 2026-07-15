"""Migration CLI — apply and generate database migrations."""

from __future__ import annotations

import asyncio
import logging
import subprocess

import click
from tortoise.migrations.api import migrate as tortoise_migrate
from tortoise.migrations.loader import MigrationLoader
from tortoise.migrations.recorder import MigrationRecorder

from vapi.lib.database import install_archive_stamp_trigger, tortoise_config

logger = logging.getLogger("vapi")


async def _apply_migrations() -> None:
    """Apply all pending migrations.

    Use ``generate_schemas`` for initial setup because Tortoise ORM's migration
    ``CreateModel`` operation silently drops foreign-key columns. Once the
    schema exists, subsequent migrations work correctly.
    """
    from tortoise import Tortoise
    from tortoise.transactions import in_transaction

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

    # Fresh database: generate the schema, install the trigger, and record the
    # migrations in one transaction so a crash never leaves a populated schema
    # without its markers (which would make the next migrate run try to re-apply
    # migrations against existing tables).
    async with in_transaction():
        await Tortoise.generate_schemas()
        # generate_schemas skips migration RunSQL; install the archive-stamp
        # trigger so fresh databases get the same DB-level backstop as migrated ones.
        await install_archive_stamp_trigger()
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
        # them all: recording only the baseline left the rest pending, and the next
        # migrate replayed them against the schema they had already produced
        # ("column ... already exists"). Skipping the SQL they carry is safe for the
        # same reason: a data migration has no rows to touch here, schema SQL only
        # restates what generate_schemas already built, and the archive trigger is
        # installed above.
        recorder = MigrationRecorder(tx_conn)
        loader = MigrationLoader(config["apps"], recorder)
        loader.load_disk()
        for key in loader.disk_migrations:
            await recorder.record_applied(key.app_label, key.name)

    await Tortoise.close_connections()


@click.command(
    name="migrate",
    help="Apply pending database migrations.",
)
def migrate() -> None:
    """Apply all pending database migrations."""
    asyncio.run(_apply_migrations())
    click.echo("Migrations applied successfully.")


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
