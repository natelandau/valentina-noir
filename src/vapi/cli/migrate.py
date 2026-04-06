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
    """Apply all pending migrations."""
    await tortoise_migrate(config=tortoise_config())


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
