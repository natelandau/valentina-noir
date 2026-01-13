"""Bootstrap utilities."""

import json
import logging

import click
from rich.console import Console

from vapi.constants import PROJECT_ROOT_PATH
from vapi.db.models import (
    AdvantageCategory,
    CharacterConcept,
    HunterEdge,
    HunterEdgePerk,
    VampireClan,
    WerewolfAuspice,
    WerewolfGift,
    WerewolfRite,
    WerewolfTribe,
)

from .utils import (
    JSONWithCommentsDecoder,
    TraitSyncResult,
    create_global_dictionary_term,
    document_differs_from_fixture,
    get_differing_fields,
    gift_link_to_tribe_and_auspice,
    link_disciplines_to_clan,
    sync_section_categories,
    sync_single_section,
)

console = Console()
logger = logging.getLogger("vapi")

FIXTURES_PATH = PROJECT_ROOT_PATH / "src/vapi/db/fixtures"


async def sync_advantage_categories() -> None:
    """Sync advantage categories."""
    fixture_file = FIXTURES_PATH / "advantage_categories.json"
    if not fixture_file.exists():
        msg = f"Fixture file not found at path: {str(fixture_file)!r}"
        logger.error(
            msg, extra={"component": "cli", "command": "bootstrap sync_advantage_categories"}
        )
        raise click.Abort

    with fixture_file.open("r") as file:
        fixture_advantage_categories = json.load(file, cls=JSONWithCommentsDecoder)

    created_count = 0
    updated_count = 0
    for fixture_category in fixture_advantage_categories:
        category = await AdvantageCategory.find_one(
            AdvantageCategory.name == fixture_category["name"]
        )
        if not category:
            category = AdvantageCategory(**fixture_category)
            await category.save()
            created_count += 1

        elif document_differs_from_fixture(category, fixture_category):
            differences = get_differing_fields(category, fixture_category)
            for field_name in differences:
                setattr(category, field_name, fixture_category[field_name])
            await category.save()
            updated_count += 1

    logger.info(
        "Bootstrapped advantage categories",
        extra={
            "num_created": created_count,
            "num_updated": updated_count,
            "num_total": len(fixture_advantage_categories),
            "component": "cli",
            "command": "bootstrap",
        },
    )


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
        category_counts, trait_counts = await sync_section_categories(fixture_section, section)
        result.categories.created += category_counts.created
        result.categories.updated += category_counts.updated
        result.categories.total += category_counts.total
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


async def sync_werewolf_gifts() -> None:
    """Sync werewolf gifts."""
    fixture_file = FIXTURES_PATH / "werewolf_gifts.json"
    if not fixture_file.exists():
        msg = f"Fixture file not found at path: {str(fixture_file)!r}"
        logger.error(msg, extra={"component": "cli", "command": "bootstrap sync_werewolf_gifts"})
        raise click.Abort

    auspices = await WerewolfAuspice.find().to_list()
    tribes = await WerewolfTribe.find().to_list()

    with fixture_file.open("r") as file:
        fixture_werewolf_gifts = json.load(file)

    created_gifts = 0
    updated_gifts = 0
    for fixture_gift in fixture_werewolf_gifts:
        created_gift = False
        gift = await WerewolfGift.find_one(WerewolfGift.name == fixture_gift["name"])
        if not gift:
            gift = WerewolfGift(**fixture_gift)
            await gift.save()
            created_gifts += 1
            created_gift = True

        elif document_differs_from_fixture(gift, fixture_gift):
            differences = get_differing_fields(gift, fixture_gift)
            for field_name in differences:
                setattr(gift, field_name, fixture_gift[field_name])
            await gift.save()

        is_updated = await gift_link_to_tribe_and_auspice(gift, fixture_gift, tribes, auspices)
        if is_updated and not created_gift:
            updated_gifts += 1

    logger.info(
        "Bootstrapped werewolf gifts",
        extra={
            "num_created": created_gifts,
            "num_updated": updated_gifts,
            "num_total": len(fixture_werewolf_gifts),
            "component": "cli",
            "command": "bootstrap",
        },
    )


async def sync_werewolf_rites() -> None:
    """Sync werewolf rites."""
    fixture_file = FIXTURES_PATH / "werewolf_rites.json"
    if not fixture_file.exists():
        msg = f"Fixture file not found at path: {str(fixture_file)!r}"
        logger.error(msg, extra={"component": "cli", "command": "bootstrap sync_werewolf_rites"})
        raise click.Abort

    with fixture_file.open("r") as file:
        fixture_werewolf_rites = json.load(file)

    created_rites = 0
    updated_rites = 0
    for fixture_rite in fixture_werewolf_rites:
        rite = await WerewolfRite.find_one(WerewolfRite.name == fixture_rite["name"])
        if not rite:
            rite = WerewolfRite(**fixture_rite)
            await rite.save()
            created_rites += 1
        elif document_differs_from_fixture(rite, fixture_rite):
            differences = get_differing_fields(rite, fixture_rite)
            for field_name in differences:
                setattr(rite, field_name, fixture_rite[field_name])
            await rite.save()
            updated_rites += 1

    logger.info(
        "Bootstrapped werewolf rites",
        extra={
            "num_created": created_rites,
            "num_updated": updated_rites,
            "num_total": len(fixture_werewolf_rites),
            "component": "cli",
            "command": "bootstrap",
        },
    )


async def sync_hunter_edges() -> None:
    """Sync hunter edges."""
    fixture_file = FIXTURES_PATH / "hunter_edges.json"
    if not fixture_file.exists():
        msg = f"Fixture file not found at path: {str(fixture_file)!r}"
        logger.error(msg, extra={"component": "cli", "command": "bootstrap sync_hunter_edges"})
        raise click.Abort

    with fixture_file.open("r") as file:
        fixture_hunter_edges = json.load(file)

    created_edges = 0
    updated_edges = 0
    created_perks = 0
    updated_perks = 0
    total_perks = 0
    for fixture_edge in fixture_hunter_edges:
        edge = await HunterEdge.find_one(HunterEdge.name == fixture_edge["name"])
        if not edge:
            edge = HunterEdge(**fixture_edge)
            await edge.save()
            created_edges += 1
        elif document_differs_from_fixture(edge, fixture_edge):
            differences = get_differing_fields(edge, fixture_edge)
            for field_name in differences:
                setattr(edge, field_name, fixture_edge[field_name])
            await edge.save()
            updated_edges += 1

        for fixture_perk in fixture_edge["perks"]:
            total_perks += 1
            perk = await HunterEdgePerk.find_one(
                HunterEdgePerk.name == fixture_perk["name"],
                HunterEdgePerk.edge_id == edge.id,
            )
            if not perk:
                perk = HunterEdgePerk(**fixture_perk)
                perk.edge_id = edge.id
                await perk.save()
                created_perks += 1
            elif document_differs_from_fixture(perk, fixture_perk):
                differences = get_differing_fields(perk, fixture_perk)
                for field_name in differences:
                    setattr(perk, field_name, fixture_perk[field_name])
                await perk.save()
                updated_perks += 1

            edge.perk_ids.append(perk.id)
            await edge.save()

    logger.info(
        "Bootstrapped hunter edges",
        extra={
            "num_created": created_edges,
            "num_updated": updated_edges,
            "num_total": len(fixture_hunter_edges),
            "component": "cli",
            "command": "bootstrap",
        },
    )
    logger.info(
        "Bootstrapped hunter edge perks",
        extra={
            "num_created": created_perks,
            "num_updated": updated_perks,
            "num_total": total_perks,
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
