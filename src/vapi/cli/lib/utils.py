"""Utilities."""

import logging
from dataclasses import dataclass, field
from typing import Any

import click

from vapi.cli.constants import dictionary_term_counts
from vapi.cli.lib.comparison import (
    JSONWithCommentsDecoder,
    document_differs_from_fixture,
    get_differing_fields,
)
from vapi.db.models import (
    CharSheetSection,
    DictionaryTerm,
    Trait,
    TraitCategory,
    TraitSubcategory,
    VampireClan,
)
from vapi.db.models.constants.trait import GiftAttributes

__all__ = (
    "JSONWithCommentsDecoder",
    "SyncCounts",
    "TraitSyncResult",
    "document_differs_from_fixture",
    "get_differing_fields",
    "link_disciplines_to_clan",
    "sync_fixture_traits",
    "sync_section_categories",
    "sync_single_category",
    "sync_single_section",
    "sync_single_trait",
)

logger = logging.getLogger("vapi")


@dataclass
class SyncCounts:
    """Track counts for sync operations."""

    created: int = 0
    updated: int = 0
    total: int = 0


@dataclass
class TraitSyncResult:
    """Result of syncing traits fixture."""

    sections: SyncCounts = field(default_factory=SyncCounts)
    categories: SyncCounts = field(default_factory=SyncCounts)
    subcategories: SyncCounts = field(default_factory=SyncCounts)
    traits: SyncCounts = field(default_factory=SyncCounts)


async def link_disciplines_to_clan(clan: VampireClan, fixture_clan: dict[str, Any]) -> bool:
    """Link disciplines to a clan."""
    is_updated = False

    if not fixture_clan.get("disciplines_to_link") and not clan.discipline_ids:
        return False

    for discipline_id in clan.discipline_ids:
        discipline = await Trait.find_one(Trait.id == discipline_id, Trait.is_archived == False)
        if not discipline:
            msg = f"Trait not found: {discipline_id}"
            logger.error(msg, extra={"component": "cli", "command": "link_disciplines_to_clan"})
            raise click.Abort
        if discipline and discipline.name not in fixture_clan.get("disciplines_to_link", []):
            clan.discipline_ids.remove(discipline_id)
            await clan.save()
            is_updated = True

    for discipline_name in fixture_clan.get("disciplines_to_link", []):
        discipline = await Trait.find_one(Trait.name == discipline_name, Trait.is_archived == False)
        if discipline and discipline.id not in clan.discipline_ids:
            clan.discipline_ids.append(discipline.id)
            await clan.save()
            is_updated = True

    return is_updated


async def sync_single_section(
    fixture_section: dict[str, Any],
) -> tuple[CharSheetSection, bool, bool]:
    """Sync a single character sheet section.

    Args:
        fixture_section (dict[str, Any]): Fixture data for the section.

    Returns:
        tuple[CharSheetSection, bool, bool]: The section, whether it was created, whether it was updated.
    """
    created = False
    updated = False

    section = await CharSheetSection.find_one(CharSheetSection.name == fixture_section["name"])
    if not section:
        section = CharSheetSection(**fixture_section)
        await section.save()
        created = True
    elif document_differs_from_fixture(section, fixture_section):
        differences = get_differing_fields(section, fixture_section)
        for field_name in differences:
            setattr(section, field_name, fixture_section[field_name])
        await section.save()
        updated = True

    return section, created, updated


async def sync_single_category(
    fixture_category: dict[str, Any],
    section: CharSheetSection,
) -> tuple[TraitCategory, bool, bool]:
    """Sync a single trait category.

    Args:
        fixture_category (dict[str, Any]): Fixture data for the category.
        section (CharSheetSection): Parent section for the category.

    Returns:
        tuple[TraitCategory, bool, bool]: The category, whether it was created, whether it was updated.
    """
    created = False
    updated = False

    category = await TraitCategory.find_one(
        TraitCategory.name == fixture_category["name"],
        TraitCategory.parent_sheet_section_id == section.id,
    )
    if not category:
        category = TraitCategory(**fixture_category, parent_sheet_section_id=section.id)

        created = True

        if not fixture_category.get("character_classes"):
            category.character_classes = section.character_classes
        if not fixture_category.get("game_versions"):
            category.game_versions = section.game_versions
        await category.save()

    elif document_differs_from_fixture(category, fixture_category):
        differences = get_differing_fields(category, fixture_category)
        for field_name in differences:
            setattr(category, field_name, fixture_category[field_name])
        await category.save()
        updated = True

    return category, created, updated


async def sync_single_subcategory(  # noqa: C901
    fixture_subcategory: dict[str, Any],
    category: TraitCategory,
) -> tuple[TraitSubcategory, bool, bool]:
    """Sync a single trait subcategory.

    Args:
        fixture_subcategory (dict[str, Any]): Fixture data for the subcategory.
        category (TraitCategory): Parent category for the subcategory.

    Returns:
        tuple[TraitSubcategory, bool, bool]: The subcategory, whether it was created, whether it was updated.
    """
    created = False
    updated = False

    subcategory = await TraitSubcategory.find_one(
        TraitSubcategory.name == fixture_subcategory["name"],
        TraitSubcategory.parent_category_id == category.id,
    )
    if not subcategory:
        subcategory = TraitSubcategory(
            **fixture_subcategory,
            parent_category_id=category.id,
            parent_category_name=category.name,
        )

        created = True

        if not fixture_subcategory.get("initial_cost"):
            subcategory.initial_cost = category.initial_cost
        if not fixture_subcategory.get("upgrade_cost"):
            subcategory.upgrade_cost = category.upgrade_cost
        if not fixture_subcategory.get("game_versions"):
            subcategory.game_versions = category.game_versions
        if not fixture_subcategory.get("character_classes"):
            subcategory.character_classes = category.character_classes

        await subcategory.save()

    elif document_differs_from_fixture(subcategory, fixture_subcategory):
        differences = get_differing_fields(subcategory, fixture_subcategory)
        for field_name in differences:
            setattr(subcategory, field_name, fixture_subcategory[field_name])
        await subcategory.save()
        updated = True

    if subcategory.description or subcategory.system or subcategory.pool:
        desc = subcategory.description or ""
        if subcategory.system:
            desc += "\n## System:\n" + subcategory.system
        if subcategory.pool:
            desc += "\n## Pool:\n" + subcategory.pool

        await create_global_dictionary_term(
            subcategory.name,
            definition=desc,
        )

    return subcategory, created, updated


def _build_gift_attributes_definition(
    gift_attributes: GiftAttributes,
    *,
    tribe_name: str | None = None,
    auspice_name: str | None = None,
) -> str:
    """Build the gift attributes portion of a trait definition.

    Args:
        gift_attributes: The gift attributes to format.
        tribe_name: Pre-resolved tribe name from the fixture.
        auspice_name: Pre-resolved auspice name from the fixture.

    Returns:
        str: Formatted gift attributes string.
    """
    cost_string = f"  - Cost: `{gift_attributes.cost or '-'}`\n" if gift_attributes.cost else ""
    duration_string = (
        f"  - Duration: `{gift_attributes.duration}`\n" if gift_attributes.duration else ""
    )
    minimum_renown_string = (
        f"  - Minimum Renown: `{gift_attributes.minimum_renown}`\n"
        if gift_attributes.minimum_renown
        else ""
    )
    tribe_string = f"  - Tribe: `{tribe_name}`\n" if tribe_name else ""
    auspice_string = f"  - Auspice: `{auspice_name}`\n" if auspice_name else ""

    result = "\n- Gift Attributes:\n"
    result += f"  - Renown: `{gift_attributes.renown.value.title()}`\n"
    result += cost_string
    result += duration_string
    result += minimum_renown_string
    result += tribe_string
    result += auspice_string
    return result


def _build_trait_definition(
    trait: Trait,
    *,
    tribe_name: str | None = None,
    auspice_name: str | None = None,
) -> str | None:
    """Build a dictionary definition string for a trait.

    Combine the trait's description, details, gift attributes, system, pool, and opposing pool
    into a formatted definition suitable for a global dictionary term.

    Args:
        trait: The trait to build a definition for.
        tribe_name: Pre-resolved tribe name from the fixture.
        auspice_name: Pre-resolved auspice name from the fixture.

    Returns:
        str | None: The formatted definition, or None if the trait has no description.
    """
    if not trait.description:
        return None

    section_string = (
        f"`{trait.sheet_section_name.title()}` > `{trait.parent_category_name.title()}`"
    )
    if trait.trait_subcategory_name:
        section_string += f" > `{trait.trait_subcategory_name.title()}`"

    pool_string = f"\n- Pool: `{trait.pool or '-'}`" if trait.pool else ""
    opposing_pool_string = (
        f"\n- Opposing Pool: `{trait.opposing_pool.title()}`" if trait.opposing_pool else ""
    )
    system_string = f"\n- System: `{trait.system or '-'}`" if trait.system else ""

    definition = f"""\
{trait.description}

### Trait Details:
- Sheet Section: {section_string}
- Character Classes: `{"`, `".join(c.title() for c in trait.character_classes)}`
- Game Versions: `{"`, `".join(v.title() for v in trait.game_versions)}`{pool_string}{opposing_pool_string}{system_string}"""

    if trait.gift_attributes:
        definition += _build_gift_attributes_definition(
            trait.gift_attributes, tribe_name=tribe_name, auspice_name=auspice_name
        )

    return definition


async def sync_single_trait(  # noqa: C901
    fixture_trait: dict[str, Any],
    *,
    category: TraitCategory,
    section: CharSheetSection,
    subcategory: TraitSubcategory | None = None,
) -> tuple[Trait, bool, bool]:
    """Sync a single trait.

    Args:
        fixture_trait (dict[str, Any]): Fixture data for the trait.
        category (TraitCategory): Parent category for the trait.
        subcategory (TraitSubcategory): Parent subcategory for the trait.
        section (CharSheetSection): Parent section for the trait.

    Returns:
        tuple[Trait, bool, bool]: The trait, whether it was created, whether it was updated.
    """
    created = False
    updated = False

    # Look up by name AND parent category to handle duplicate names across categories
    query = [
        Trait.name == fixture_trait["name"].strip().title(),
        Trait.parent_category_id == category.id,
    ]
    if subcategory:
        query.append(Trait.trait_subcategory_id == subcategory.id)

    trait = await Trait.find_one(*query)

    # Convert gift_attributes dict to GiftAttributes object, stripping fixture-only fields.
    # tribe_id/auspice_id are resolved later by resolve_gift_trait_references()
    # after WerewolfTribe/WerewolfAuspice documents exist in the database.
    gift_attrs_raw = fixture_trait.pop("gift_attributes", None)
    gift_tribe_name: str | None = None
    gift_auspice_name: str | None = None
    if gift_attrs_raw is not None:
        gift_tribe_name = gift_attrs_raw.pop("tribe_name", None)
        gift_auspice_name = gift_attrs_raw.pop("auspice_name", None)
        fixture_trait["gift_attributes"] = GiftAttributes(**gift_attrs_raw)

    if not trait:
        trait = Trait(
            **fixture_trait,
            parent_category_id=category.id,
            parent_category_name=category.name,
            sheet_section_id=section.id,
            sheet_section_name=section.name,
            trait_subcategory_id=subcategory.id if subcategory else None,
            trait_subcategory_name=subcategory.name if subcategory else None,
        )
        # Apply default costs from category if not specified
        if not fixture_trait.get("initial_cost"):
            trait.initial_cost = (
                subcategory.initial_cost if subcategory else category.initial_cost or 1
            )
        if not fixture_trait.get("upgrade_cost"):
            trait.upgrade_cost = (
                subcategory.upgrade_cost if subcategory else category.upgrade_cost or 1
            )
        if not fixture_trait.get("game_versions"):
            trait.game_versions = (
                subcategory.game_versions if subcategory else category.game_versions or []
            )
        if not fixture_trait.get("character_classes"):
            trait.character_classes = (
                subcategory.character_classes if subcategory else category.character_classes or []
            )
        if not fixture_trait.get("pool"):
            trait.pool = subcategory.pool if subcategory and subcategory.pool else None
        if not fixture_trait.get("system"):
            trait.system = subcategory.system if subcategory and subcategory.system else None
        await trait.save()
        created = True

    elif document_differs_from_fixture(trait, fixture_trait):
        differences = get_differing_fields(trait, fixture_trait)
        for field_name in differences:
            setattr(trait, field_name, fixture_trait[field_name])
        await trait.save()
        updated = True

    definition = _build_trait_definition(
        trait, tribe_name=gift_tribe_name, auspice_name=gift_auspice_name
    )

    if definition or trait.link:
        await create_global_dictionary_term(
            term=trait.name,
            definition=definition,
            link=trait.link or None,
        )

    return trait, created, updated


async def sync_fixture_traits(
    fixture_data: dict[str, Any],
    *,
    category: TraitCategory,
    section: CharSheetSection,
    subcategory: TraitSubcategory | None = None,
) -> SyncCounts:
    """Sync all traits from a fixture data dict (category or subcategory level).

    Args:
        fixture_data: Fixture data containing a "traits" key.
        category: The parent category for the traits.
        section: The parent section for the traits.
        subcategory: Optional parent subcategory for the traits.

    Returns:
        SyncCounts: Counts of created, updated, and total traits.
    """
    counts = SyncCounts()

    for fixture_trait in fixture_data.get("traits", []):
        _, created, updated = await sync_single_trait(
            fixture_trait=fixture_trait,
            category=category,
            section=section,
            subcategory=subcategory,
        )
        counts.total += 1
        if created:
            counts.created += 1
        elif updated:
            counts.updated += 1

    return counts


async def sync_section_categories(
    fixture_section: dict[str, Any],
    section: CharSheetSection,
) -> tuple[SyncCounts, SyncCounts, SyncCounts]:
    """Sync all categories and their traits within a section.

    Args:
        fixture_section (dict[str, Any]): Fixture data for the section.
        section (CharSheetSection): The section to sync categories for.

    Returns:
        tuple[SyncCounts, SyncCounts, SyncCounts]: Counts for categories, subcategories, and traits.
    """
    category_counts = SyncCounts()
    subcategory_counts = SyncCounts()
    trait_counts = SyncCounts()

    for fixture_category in fixture_section.get("categories", []):
        category, created, updated = await sync_single_category(fixture_category, section)

        category_counts.total += 1
        if created:
            category_counts.created += 1
        elif updated:
            category_counts.updated += 1

        for fixture_subcategory in fixture_category.get("subcategories", []):
            subcategory, created, updated = await sync_single_subcategory(
                fixture_subcategory, category
            )
            subcategory_counts.total += 1
            if created:
                subcategory_counts.created += 1
            elif updated:
                subcategory_counts.updated += 1

            subcategory_traits_result = await sync_fixture_traits(
                fixture_subcategory, subcategory=subcategory, category=category, section=section
            )
            trait_counts.created += subcategory_traits_result.created
            trait_counts.updated += subcategory_traits_result.updated
            trait_counts.total += subcategory_traits_result.total

        # Sync traits within this category
        traits_result = await sync_fixture_traits(
            fixture_category, category=category, section=section
        )
        trait_counts.created += traits_result.created
        trait_counts.updated += traits_result.updated
        trait_counts.total += traits_result.total

    return category_counts, subcategory_counts, trait_counts


async def create_global_dictionary_term(
    term: str, *, definition: str | None = None, link: str | None = None
) -> None:
    """Create a global dictionary term."""
    if not definition and not link:
        return

    existing_term = await DictionaryTerm.find_one(
        DictionaryTerm.term == term.lower().strip(), DictionaryTerm.is_global == True
    )
    if not existing_term:
        await DictionaryTerm(
            term=term.lower().strip(),
            definition=definition.strip() if definition else None,
            link=link.strip() if link else None,
            is_global=True,
        ).insert()
        dictionary_term_counts["created"] += 1
        dictionary_term_counts["total"] += 1
    elif existing_term.definition != definition or existing_term.link != link:
        await existing_term.update(
            {
                "$set": {
                    "definition": definition.strip() if definition else None,
                    "link": link.strip() if link else None,
                }
            }
        )
        dictionary_term_counts["updated"] += 1
        dictionary_term_counts["total"] += 1
