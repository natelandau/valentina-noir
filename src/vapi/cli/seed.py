"""Seed CLI — sync reference/fixture data into the database."""

from __future__ import annotations

import logging

import click

from vapi.cli.lib.dictionary import DictionaryService
from vapi.cli.lib.fixture_syncer import (
    CharacterConceptSyncer,
    VampireClanSyncer,
    WerewolfAuspiceSyncer,
    WerewolfTribeSyncer,
)
from vapi.cli.lib.runner import run_with_tortoise
from vapi.cli.lib.trait_syncer import TraitSyncer, resolve_gift_trait_references

logger = logging.getLogger("vapi")


async def seed_async() -> None:
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


@click.command(
    name="seed",
    help="Seed the database with reference data. Run after migrations when fixture data changes.",
)
def seed() -> None:
    """Seed everything."""
    run_with_tortoise(seed_async())
