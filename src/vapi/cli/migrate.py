"""Migration CLI — apply and generate database migrations."""

from __future__ import annotations

import asyncio
import logging
import subprocess

import click
from tortoise.migrations.api import migrate as tortoise_migrate

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
    # baseline migration in one transaction so a crash never leaves a populated
    # schema without its 0001_initial marker (which would make the next migrate
    # run try to re-apply 0001_initial against existing tables).
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
            "INSERT INTO tortoise_migrations (app, name) VALUES ('models', '0001_initial');"
        )

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
