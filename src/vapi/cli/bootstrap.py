"""Admin CLI."""

from __future__ import annotations

import asyncio
import logging

import click

from vapi.cli.lib.dictionary import DictionaryService
from vapi.cli.lib.fixture_syncer import (
    CharacterConceptSyncer,
    VampireClanSyncer,
    WerewolfAuspiceSyncer,
    WerewolfTribeSyncer,
)
from vapi.cli.lib.trait_syncer import TraitSyncer, resolve_gift_trait_references
from vapi.lib.database import setup_database

logger = logging.getLogger("vapi")


async def bootstrap_async(*, do_setup_database: bool = True) -> None:
    """The bootstrap function."""
    if do_setup_database:
        await setup_database()

    trait_syncer = TraitSyncer()
    await trait_syncer.sync()
    await VampireClanSyncer().sync()
    await WerewolfAuspiceSyncer().sync()
    await WerewolfTribeSyncer().sync()
    await resolve_gift_trait_references(gift_fixture_map=trait_syncer.gift_fixture_map)
    await CharacterConceptSyncer().sync()
    await DictionaryService().sync_all()


@click.command(
    name="bootstrap",
    help="Bootstrap the database. Do this on first run or when the version of the application changes.",
)
def bootstrap() -> None:
    """Bootstrap everything."""
    asyncio.run(bootstrap_async())
