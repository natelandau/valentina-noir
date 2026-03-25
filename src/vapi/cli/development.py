"""Development CLI."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.prompt import Confirm

from vapi.config import settings
from vapi.lib.database import setup_database

from .bootstrap import bootstrap_async
from .lib.population import PopulationService

if TYPE_CHECKING:
    from pymongo import AsyncMongoClient

logger = logging.getLogger("vapi")
console = Console()


@click.group(name="dev", invoke_without_command=False, help="development commands")
def development_group() -> None:
    """Development CLI."""


async def _purge_db_async(client: AsyncMongoClient) -> None:
    await client.drop_database(settings.mongo.database_name)
    logger.info("Database purged", extra={"component": "cli", "command": "purge_db"})


@development_group.command(name="purgedb", help="Purge the database")
def purge_db() -> None:
    """Purge the database."""
    confirm = Confirm.ask(
        f"Are you sure you want to purge the database located at [green bold]{settings.mongo.uri}/{settings.mongo.database_name}[/green bold]?"
    )
    if not confirm:
        click.echo("Aborting...")
        return

    async def purge_db_async() -> None:
        client = await setup_database()
        await _purge_db_async(client)

    asyncio.run(purge_db_async())
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
    confirm = Confirm.ask(
        f"Are you sure you want to purge and populate the database at [green bold]{settings.mongo.uri}/{settings.mongo.database_name}[/green bold]"
    )
    if not confirm:
        console.print("Aborting...")
        return

    async def populate_db_async() -> None:
        """Populate the database."""
        # First we setup the database and purge it
        client = await setup_database()
        await _purge_db_async(client)

        # Then we bootstrap the database with the necessary data
        await bootstrap_async(do_setup_database=False)

        # Then we populate the database with dummy data
        service = PopulationService()
        await service.populate(
            num_companies=num_companies,
            num_users=num_users,
            num_campaigns=num_campaigns,
            num_characters=num_characters,
        )

    asyncio.run(populate_db_async())
