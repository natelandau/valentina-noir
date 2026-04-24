"""Development CLI."""

from __future__ import annotations

import asyncio
import logging

import click
from rich.console import Console
from rich.prompt import Confirm
from tortoise import Tortoise

from vapi.config import settings
from vapi.lib.database import drop_and_recreate_database, init_tortoise

from .lib.population import PopulationService
from .seed import seed_async

logger = logging.getLogger("vapi")
console = Console()


@click.group(name="dev", invoke_without_command=False, help="development commands")
def development_group() -> None:
    """Development CLI."""


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

    asyncio.run(drop_and_recreate_database())
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
        await drop_and_recreate_database()

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
