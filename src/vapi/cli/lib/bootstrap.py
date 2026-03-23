"""Bootstrap utilities."""

import json
import logging

import click
from rich.console import Console

from vapi.constants import PROJECT_ROOT_PATH
from vapi.db.models import (
    CharacterConcept,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)

from .utils import (
    JSONWithCommentsDecoder,
    TraitSyncResult,
    create_global_dictionary_term,
    document_differs_from_fixture,
    get_differing_fields,
    link_disciplines_to_clan,
    sync_section_categories,
    sync_single_section,
)

console = Console()
logger = logging.getLogger("vapi")

FIXTURES_PATH = PROJECT_ROOT_PATH / "src/vapi/db/fixtures"


async def sync_traits() -> None:
    """Sync traits from fixture file to database.

    Load sections, categories, and traits from the traits.json fixture and
    synchronize them with the database, creating new entities or updating
    existing ones as needed.
    """
    fixture_file = FIXTURES_PATH / "traits.json"
    if not fixture_file.exists():
        msg = f"Fixture file not found at path: {str(fixture_file)!r}"
        logger.error(msg, extra={"component": "cli", "command": "bootstrap sync_traits"})
        raise click.Abort

    with fixture_file.open("r") as file:
        fixture_traits = json.load(file, cls=JSONWithCommentsDecoder)

    result = TraitSyncResult()

    for fixture_section in fixture_traits:
        section, created, updated = await sync_single_section(fixture_section)
        result.sections.total += 1
        if created:
            result.sections.created += 1
        elif updated:
            result.sections.updated += 1

        # Sync categories and traits within this section
        category_counts, subcategory_counts, trait_counts = await sync_section_categories(
            fixture_section, section
        )
        result.categories.created += category_counts.created
        result.categories.updated += category_counts.updated
        result.categories.total += category_counts.total
        result.subcategories.created += subcategory_counts.created
        result.subcategories.updated += subcategory_counts.updated
        result.subcategories.total += subcategory_counts.total
        result.traits.created += trait_counts.created
        result.traits.updated += trait_counts.updated
        result.traits.total += trait_counts.total

    logger.info(
        "Bootstrapped character sheet sections",
        extra={
            "num_created": result.sections.created,
            "num_updated": result.sections.updated,
            "num_total": result.sections.total,
            "component": "cli",
            "command": "bootstrap",
        },
    )
    logger.info(
        "Bootstrapped Trait categories",
        extra={
            "num_created": result.categories.created,
            "num_updated": result.categories.updated,
            "num_total": result.categories.total,
            "component": "cli",
            "command": "bootstrap",
        },
    )
    logger.info(
        "Bootstrapped Trait subcategories",
        extra={
            "num_created": result.subcategories.created,
            "num_updated": result.subcategories.updated,
            "num_total": result.subcategories.total,
            "component": "cli",
            "command": "bootstrap",
        },
    )
    logger.info(
        "Bootstrapped Traits",
        extra={
            "num_created": result.traits.created,
            "num_updated": result.traits.updated,
            "num_total": result.traits.total,
            "component": "cli",
            "command": "bootstrap",
        },
    )


async def sync_vampire_clans() -> None:
    """Sync vampire clans."""
    fixture_file = FIXTURES_PATH / "vampire_clans.json"
    if not fixture_file.exists():
        msg = f"Fixture file not found at path: {str(fixture_file)!r}"
        logger.error(msg, extra={"component": "cli", "command": "bootstrap sync_vampire_clans"})
        raise click.Abort

    with fixture_file.open("r") as file:
        fixture_vampire_clans = json.load(file)

    created_clans = 0
    updated_clans = 0
    for fixture_clan in fixture_vampire_clans:
        await create_global_dictionary_term(
            fixture_clan["name"],
            definition=fixture_clan.get("description"),
            link=fixture_clan.get("link"),
        )

        created_clan = False
        clan = await VampireClan.find_one(VampireClan.name == fixture_clan["name"])

        if not clan:
            clan = VampireClan(**fixture_clan)
            await clan.save()
            created_clans += 1
            created_clan = True
        elif document_differs_from_fixture(clan, fixture_clan):
            differences = get_differing_fields(clan, fixture_clan)
            for field_name in differences:
                setattr(clan, field_name, fixture_clan[field_name])
            await clan.save()
            updated_clans += 1

        is_updated = await link_disciplines_to_clan(clan, fixture_clan)
        if is_updated and not created_clan:
            updated_clans += 1

    logger.info(
        "Bootstrapped vampire clans",
        extra={
            "num_created": created_clans,
            "num_updated": updated_clans,
            "num_total": len(fixture_vampire_clans),
            "component": "cli",
            "command": "bootstrap",
        },
    )


async def sync_werewolf_auspices() -> None:
    """Sync werewolf auspices."""
    fixture_file = FIXTURES_PATH / "werewolf_auspices.json"
    if not fixture_file.exists():
        msg = f"Fixture file not found at path: {str(fixture_file)!r}"
        logger.error(msg, extra={"component": "cli", "command": "bootstrap sync_werewolf_auspices"})
        raise click.Abort

    with fixture_file.open("r") as file:
        fixture_werewolf_auspices = json.load(file)

    created_auspices = 0
    updated_auspices = 0
    for fixture_auspice in fixture_werewolf_auspices:
        await create_global_dictionary_term(
            fixture_auspice["name"],
            definition=fixture_auspice.get("description"),
            link=fixture_auspice.get("link"),
        )

        auspice = await WerewolfAuspice.find_one(WerewolfAuspice.name == fixture_auspice["name"])
        if not auspice:
            auspice = WerewolfAuspice(**fixture_auspice)
            await auspice.save()
            created_auspices += 1
        elif document_differs_from_fixture(auspice, fixture_auspice):
            differences = get_differing_fields(auspice, fixture_auspice)
            for field_name in differences:
                setattr(auspice, field_name, fixture_auspice[field_name])
            await auspice.save()
            updated_auspices += 1

    logger.info(
        "Bootstrapped werewolf auspices",
        extra={
            "num_created": created_auspices,
            "num_updated": updated_auspices,
            "num_total": len(fixture_werewolf_auspices),
            "component": "cli",
            "command": "bootstrap",
        },
    )


async def sync_werewolf_tribes() -> None:
    """Sync werewolf tribes."""
    fixture_file = FIXTURES_PATH / "werewolf_tribes.json"
    if not fixture_file.exists():
        msg = f"Fixture file not found at path: {str(fixture_file)!r}"
        logger.error(msg, extra={"component": "cli", "command": "bootstrap sync_werewolf_tribes"})
        raise click.Abort

    with fixture_file.open("r") as file:
        fixture_werewolf_tribes = json.load(file)

    created_tribes = 0
    updated_tribes = 0
    for fixture_tribe in fixture_werewolf_tribes:
        await create_global_dictionary_term(
            fixture_tribe["name"],
            definition=fixture_tribe.get("description"),
            link=fixture_tribe.get("link"),
        )

        tribe = await WerewolfTribe.find_one(WerewolfTribe.name == fixture_tribe["name"])
        if not tribe:
            tribe = WerewolfTribe(**fixture_tribe)
            await tribe.save()
            created_tribes += 1

        elif document_differs_from_fixture(tribe, fixture_tribe):
            differences = get_differing_fields(tribe, fixture_tribe)
            for field_name in differences:
                setattr(tribe, field_name, fixture_tribe[field_name])
            await tribe.save()
            updated_tribes += 1

    logger.info(
        "Bootstrapped werewolf tribes",
        extra={
            "num_created": created_tribes,
            "num_updated": updated_tribes,
            "num_total": len(fixture_werewolf_tribes),
            "component": "cli",
            "command": "bootstrap",
        },
    )


async def sync_character_concepts() -> None:
    """Sync character concepts."""
    fixture_file = FIXTURES_PATH / "concepts.json"
    if not fixture_file.exists():
        msg = f"Fixture file not found at path: {str(fixture_file)!r}"
        logger.error(
            msg, extra={"component": "cli", "command": "bootstrap sync_character_concepts"}
        )
        raise click.Abort

    with fixture_file.open("r") as file:
        fixture_character_concepts = json.load(file)

    created_concepts = 0
    updated_concepts = 0
    for fixture_concept in fixture_character_concepts:
        concept = await CharacterConcept.find_one(CharacterConcept.name == fixture_concept["name"])
        if not concept:
            concept = CharacterConcept(**fixture_concept)
            await concept.save()
            created_concepts += 1
        elif document_differs_from_fixture(concept, fixture_concept):
            # Optional: log the differences for debugging
            differences = get_differing_fields(concept, fixture_concept)
            for field_name in differences:
                setattr(concept, field_name, fixture_concept[field_name])
            await concept.save()
            updated_concepts += 1

    logger.info(
        "Bootstrapped character concepts",
        extra={
            "num_created": created_concepts,
            "num_updated": updated_concepts,
            "num_total": len(fixture_character_concepts),
            "component": "cli",
            "command": "bootstrap",
        },
    )
