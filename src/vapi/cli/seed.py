"""Seed CLI — sync reference/fixture data into the database."""

from __future__ import annotations

import logging

import click
from tortoise.transactions import in_transaction

from vapi.cli.lib.dictionary import DictionaryService
from vapi.cli.lib.fixture_syncer import (
    CharacterConceptSyncer,
    VampireClanSyncer,
    WerewolfAuspiceSyncer,
    WerewolfTribeSyncer,
)
from vapi.cli.lib.gift_syncer import resolve_gift_trait_references
from vapi.cli.lib.runner import run_with_tortoise
from vapi.cli.lib.trait_syncer import TraitSyncer
from vapi.lib.reference_data import record_reference_data_seed

logger = logging.getLogger("vapi")


async def seed_async() -> None:
    """Seed PostgreSQL with all constant and reference data via Tortoise ORM.

    Run every syncer in one transaction so a failure partway leaves the reference data exactly
    as it was, never half-updated. Assumes Tortoise is already initialized.
    """
    async with in_transaction():
        trait_syncer = TraitSyncer()
        await trait_syncer.sync()
        await VampireClanSyncer().sync()
        await WerewolfAuspiceSyncer().sync()
        await WerewolfTribeSyncer().sync()
        await resolve_gift_trait_references(gift_fixture_map=trait_syncer.gift_fixture_map)
        await CharacterConceptSyncer().sync()
        await DictionaryService().sync_all()
        await record_reference_data_seed()


@click.command(
    name="seed",
    help="Seed the database with reference data. `app migrate` also runs this after migrating.",
)
def seed() -> None:
    """Seed everything."""
    run_with_tortoise(seed_async())
