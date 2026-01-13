"""Admin CLI."""

from __future__ import annotations

import asyncio
import logging

import click
from rich.console import Console

from vapi.cli.constants import dictionary_term_counts
from vapi.lib.database import setup_database

from .lib import bootstrap as utils

console = Console()
logger = logging.getLogger("vapi")


async def bootstrap_async(*, do_setup_database: bool = True) -> None:
    """The bootstrap function.

    Args:
        do_setup_database (bool): Whether to setup the database. Defaults to True.

    Commands need to be run in the following order because they are dependent on each other:

    1. Advantage Categories
    2. Traits
    3. Vampire Clans
    4. Werewolf Aspirices
    5. Werewolf Tribes
    6. Werewolf Gifts
    7. Character Concepts
    """
    if do_setup_database:
        await setup_database()

    await utils.sync_advantage_categories()
    await utils.sync_traits()
    await utils.sync_vampire_clans()
    await utils.sync_werewolf_auspices()
    await utils.sync_werewolf_tribes()
    await utils.sync_werewolf_gifts()
    await utils.sync_werewolf_rites()
    await utils.sync_hunter_edges()
    await utils.sync_character_concepts()

    logger.info(
        "Dictionary terms",
        extra={
            "num_created": dictionary_term_counts["created"],
            "num_updated": dictionary_term_counts["updated"],
            "num_total": dictionary_term_counts["created"] + dictionary_term_counts["updated"],
            "component": "cli",
            "command": "bootstrap",
        },
    )


@click.command(
    name="bootstrap",
    help="Bootstrap the database. Do this on first run or when the version of the application changes.",
)
def bootstrap() -> None:
    """Bootstrap everything."""
    asyncio.run(bootstrap_async())
