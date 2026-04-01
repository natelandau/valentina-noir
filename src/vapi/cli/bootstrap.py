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
from vapi.cli.lib.pg.dictionary import PgDictionaryService
from vapi.cli.lib.pg.fixture_syncer import (
    PgCharacterConceptSyncer,
    PgVampireClanSyncer,
    PgWerewolfAuspiceSyncer,
    PgWerewolfTribeSyncer,
)
from vapi.cli.lib.pg.trait_syncer import PgTraitSyncer, pg_resolve_gift_trait_references
from vapi.cli.lib.trait_syncer import TraitSyncer, resolve_gift_trait_references
from vapi.lib.database import setup_database
from vapi.lib.postgres_database import tortoise_config

logger = logging.getLogger("vapi")


async def bootstrap_async(*, do_setup_database: bool = True) -> None:
    """Seed MongoDB with all constant and reference data via Beanie ORM."""
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


async def pg_bootstrap_async() -> None:
    """Bootstrap PostgreSQL with all constant and reference data.

    Sync the full trait hierarchy, character class constants, concepts,
    and dictionary terms into PostgreSQL via Tortoise ORM. Assumes Tortoise
    is already initialized.
    """
    trait_syncer = PgTraitSyncer()
    await trait_syncer.sync()
    await PgVampireClanSyncer().sync()
    await PgWerewolfAuspiceSyncer().sync()
    await PgWerewolfTribeSyncer().sync()
    await pg_resolve_gift_trait_references(gift_fixture_map=trait_syncer.gift_fixture_map)
    await PgCharacterConceptSyncer().sync()
    await PgDictionaryService().sync_all()


async def _bootstrap_all() -> None:
    """Run both MongoDB and PostgreSQL bootstrap phases.

    Initializes Tortoise ORM, seeds both databases, then closes Tortoise
    connections for clean CLI shutdown.
    """
    await bootstrap_async()
    await Tortoise.init(config=tortoise_config())
    await Tortoise.generate_schemas(safe=True)
    await pg_bootstrap_async()
    await Tortoise.close_connections()


@click.command(
    name="bootstrap",
    help="Bootstrap the database. Do this on first run or when the version of the application changes.",
)
def bootstrap() -> None:
    """Bootstrap everything."""
    asyncio.run(_bootstrap_all())
