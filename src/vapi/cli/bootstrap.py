"""Admin CLI."""

from __future__ import annotations

import asyncio
import logging

import click
from tortoise import Tortoise

from vapi.cli.lib.dictionary import DictionaryService
from vapi.cli.lib.fixture_syncer import (
    CharacterConceptSyncer,
    VampireClanSyncer,
    WerewolfAuspiceSyncer,
    WerewolfTribeSyncer,
)
from vapi.cli.lib.trait_syncer import TraitSyncer, resolve_gift_trait_references
from vapi.lib.database import tortoise_config

logger = logging.getLogger("vapi")


async def bootstrap_async() -> None:
    """Seed PostgreSQL with all constant and reference data via Tortoise ORM.

    Assumes Tortoise is already initialized.
    """
    trait_syncer = TraitSyncer()
    await trait_syncer.sync()
    await VampireClanSyncer().sync()
    await WerewolfAuspiceSyncer().sync()
    await WerewolfTribeSyncer().sync()
    await resolve_gift_trait_references(gift_fixture_map=trait_syncer.gift_fixture_map)
    await CharacterConceptSyncer().sync()
    await DictionaryService().sync_all()


async def _bootstrap_all() -> None:
    """Run the full PostgreSQL bootstrap.

    Initializes Tortoise ORM, seeds the database, then closes Tortoise
    connections for clean CLI shutdown.
    """
    await Tortoise.init(config=tortoise_config())
    await Tortoise.generate_schemas(safe=True)
    await bootstrap_async()
    await Tortoise.close_connections()


@click.command(
    name="bootstrap",
    help="Bootstrap the database. Do this on first run or when the version of the application changes.",
)
def bootstrap() -> None:
    """Bootstrap everything."""
    asyncio.run(_bootstrap_all())
