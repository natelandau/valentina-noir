"""Development CLI."""

from __future__ import annotations

import asyncio
import logging

import click
from rich.console import Console
from rich.prompt import Confirm
from tortoise import Tortoise

from vapi.config import settings
from vapi.lib.database import init_tortoise

from .lib.population import PopulationService
from .seed import seed_async

logger = logging.getLogger("vapi")
console = Console()


@click.group(name="dev", invoke_without_command=False, help="development commands")
def development_group() -> None:
    """Development CLI."""


async def _purge_pg_async() -> None:
    """Drop and recreate the entire PostgreSQL database.

    Connects to the ``postgres`` maintenance database to execute DROP/CREATE,
    since you cannot drop a database while connected to it.
    """
    import asyncpg

    pg = settings.postgres
    conn = await asyncpg.connect(
        host=pg.host,
        port=pg.port,
        user=pg.user,
        password=pg.password,
        database="postgres",
    )
    try:
        # Terminate existing connections so the DROP succeeds
        terminate_sql = f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{pg.database}' AND pid <> pg_backend_pid()"  # noqa: S608
        await conn.execute(terminate_sql)
        await conn.execute(f'DROP DATABASE IF EXISTS "{pg.database}"')
        await conn.execute(f'CREATE DATABASE "{pg.database}" OWNER {pg.user}')
    finally:
        await conn.close()


@development_group.command(name="purgedb", help="Purge the database")
def purge_db() -> None:
    """Purge the database."""
    pg = settings.postgres
    confirm = Confirm.ask(
        f"Are you sure you want to purge the database at [green bold]{pg.host}:{pg.port}/{pg.database}[/green bold]?"
    )
    if not confirm:
        click.echo("Aborting...")
        return

    asyncio.run(_purge_pg_async())
    click.echo("Database purged")


@development_group.command(name="populate", help="Populate the database with dummy data")
@click.option(
    "--companies", "num_companies", type=int, default=1, help="Number of companies to create"
)
@click.option(
    "--users",
    "num_users",
    type=int,
    default=1,
    help="Number of users to create per company",
)
@click.option(
    "--campaigns",
    "num_campaigns",
    type=int,
    default=1,
    help="Number of campaigns to create per company",
)
@click.option(
    "--characters",
    "num_characters",
    type=int,
    default=1,
    help="Number of characters to create per campaign",
)
def populate_db(
    *, num_companies: int, num_users: int, num_campaigns: int, num_characters: int
) -> None:
    """Populate the database with dummy data."""
    pg = settings.postgres
    confirm = Confirm.ask(
        f"Are you sure you want to purge and populate the database at [green bold]{pg.host}:{pg.port}/{pg.database}[/green bold]?"
    )
    if not confirm:
        console.print("Aborting...")
        return

    async def populate_db_async() -> None:
        """Populate the database."""
        # First purge the database
        await _purge_pg_async()

        # Then seed and populate
        await init_tortoise()
        await Tortoise.generate_schemas(safe=True)
        await seed_async()
        try:
            service = PopulationService()
            await service.populate(
                num_companies=num_companies,
                num_users=num_users,
                num_campaigns=num_campaigns,
                num_characters=num_characters,
            )
        finally:
            await Tortoise.close_connections()

    asyncio.run(populate_db_async())
