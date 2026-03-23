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

    1. Traits (needed by vampire clans for discipline linking)
    2. Vampire Clans
    3. Werewolf Auspices
    4. Werewolf Tribes
    5. Resolve gift trait tribe/auspice IDs (must run after auspices/tribes exist)
    6. Character Concepts
    """
    if do_setup_database:
        await setup_database()

    await utils.sync_traits()
    await utils.sync_vampire_clans()
    await utils.sync_werewolf_auspices()
    await utils.sync_werewolf_tribes()
    await utils.resolve_gift_trait_references()
    await utils.sync_character_concepts()

    logger.info(
        "Dictionary terms",
        extra={
            "num_created": dictionary_term_counts["created"],
            "num_updated": dictionary_term_counts["updated"],
            "num_total": dictionary_term_counts["total"],
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
