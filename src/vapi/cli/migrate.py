"""Migration CLI — apply and generate database migrations."""

from __future__ import annotations

import asyncio
import logging
import subprocess

import click
from tortoise.migrations.api import migrate as tortoise_migrate

from vapi.lib.database import tortoise_config

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

    conn = Tortoise.get_connection("default")
    try:
        _, rows = await conn.execute_query(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'trait')"
        )
        tables_exist = rows[0]["exists"]
    except Exception:  # noqa: BLE001
        tables_exist = False

    if not tables_exist:
        await Tortoise.generate_schemas()
        # Record the initial migration so future migrations know it was applied
        await conn.execute_script(
            "CREATE TABLE IF NOT EXISTS tortoise_migrations ("
            "  id SERIAL PRIMARY KEY,"
            "  app VARCHAR(100) NOT NULL,"
            "  name VARCHAR(255) NOT NULL,"
            "  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
            ");"
            "INSERT INTO tortoise_migrations (app, name) VALUES ('models', '0001_initial');"
        )
    else:
        await Tortoise.close_connections()
        await tortoise_migrate(config=config)
        return

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
