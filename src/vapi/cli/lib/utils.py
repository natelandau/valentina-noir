"""Utilities."""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

import click
from beanie import Document
from pydantic import BaseModel

from vapi.cli.constants import dictionary_term_counts
from vapi.db.models import (
    AdvantageCategory,
    CharSheetSection,
    DictionaryTerm,
    Trait,
    TraitCategory,
    VampireClan,
    WerewolfAuspice,
    WerewolfGift,
    WerewolfTribe,
)

T = TypeVar("T", bound=Document)

__all__ = (
    "JSONWithCommentsDecoder",
    "SyncCounts",
    "TraitSyncResult",
    "document_differs_from_fixture",
    "get_differing_fields",
    "gift_link_to_tribe_and_auspice",
    "link_disciplines_to_clan",
    "sync_category_traits",
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


async def gift_link_to_tribe_and_auspice(  # noqa: C901, PLR0912
    gift: WerewolfGift,
    fixture_gift: dict[str, Any],
    tribes: list[WerewolfTribe],
    auspices: list[WerewolfAuspice],
) -> bool:
    """Link a gift to a tribe and auspice.

    Args:
        gift (WerewolfGift): The gift to link to a tribe and auspice.
        fixture_gift (dict[str, Any]): The fixture data for the gift.
        tribes (list[WerewolfTribe]): The list of tribes to link the gift to.
        auspices (list[WerewolfAuspice]): The list of auspices to link the gift to.

    Returns:
        bool: True if the gift was linked to a tribe and auspice, False otherwise.
    """
    is_updated = False
    tribe_name = fixture_gift.get("tribe_name")
    auspice_name = fixture_gift.get("auspice_name")
    if not tribe_name and not auspice_name:
        return False

    if tribe_name:
        requested_tribe = next((tribe for tribe in tribes if tribe.name == tribe_name), None)
        if not requested_tribe:
            msg = f"Tribe not found: {tribe_name}"
            logger.error(
                msg, extra={"component": "cli", "command": "gift_link_to_tribe_and_auspice"}
            )
            raise click.Abort
        if gift.tribe_id and gift.tribe_id != requested_tribe.id:
            old_tribe = await WerewolfTribe.find_one(WerewolfTribe.id == gift.tribe_id)
            if old_tribe and gift.id in old_tribe.gift_ids:
                old_tribe.gift_ids.remove(gift.id)
                await old_tribe.save()
        if gift.id not in requested_tribe.gift_ids:
            requested_tribe.gift_ids.append(gift.id)
            await requested_tribe.save()
        if gift.tribe_id != requested_tribe.id:
            gift.tribe_id = requested_tribe.id
            await gift.save()
            is_updated = True

    if auspice_name:
        requested_auspice = next(
            (auspice for auspice in auspices if auspice.name == auspice_name),
            None,
        )
        if not requested_auspice:
            msg = f"Auspice not found: {auspice_name}"
            logger.error(
                msg, extra={"component": "cli", "command": "gift_link_to_tribe_and_auspice"}
            )
            raise click.Abort
        if gift.auspice_id and gift.auspice_id != requested_auspice.id:
            old_auspice = await WerewolfAuspice.find_one(WerewolfAuspice.id == gift.auspice_id)
            if old_auspice and gift.id in old_auspice.gift_ids:
                old_auspice.gift_ids.remove(gift.id)
                await old_auspice.save()
        if gift.id not in requested_auspice.gift_ids:
            requested_auspice.gift_ids.append(gift.id)
            await requested_auspice.save()
        if gift.auspice_id != requested_auspice.id:
            gift.auspice_id = requested_auspice.id
            await gift.save()
            is_updated = True

    return is_updated


def _normalize_value(value: Any) -> Any:
    """Normalize a value for comparison.

    Converts enums to their values, Pydantic models to dicts, and recursively
    normalizes nested structures.

    Args:
        value (Any): The value to normalize.

    Returns:
        Any: The normalized value suitable for comparison.
    """
    if value is None:
        return None

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, BaseModel):
        return {k: _normalize_value(v) for k, v in value.model_dump().items()}

    if isinstance(value, list):
        return [_normalize_value(item) for item in value]

    if isinstance(value, dict):
        return {k: _normalize_value(v) for k, v in value.items()}

    return value


def _values_equal(model_value: Any, fixture_value: Any) -> bool:
    """Compare two values after normalization.

    Args:
        model_value (Any): The value from the database model.
        fixture_value (Any): The value from the fixture JSON.

    Returns:
        bool: True if values are equal, False otherwise.
    """
    normalized_model = _normalize_value(model_value)
    normalized_fixture = _normalize_value(fixture_value)

    # Handle list of dicts - compare as unordered sets
    if (
        isinstance(normalized_model, list)
        and normalized_model
        and isinstance(normalized_model[0], dict)
    ):
        if not isinstance(normalized_fixture, list) or len(normalized_model) != len(
            normalized_fixture
        ):
            return False

        try:
            model_set = {frozenset(_flatten_dict(d).items()) for d in normalized_model}
            fixture_set = {frozenset(_flatten_dict(d).items()) for d in normalized_fixture}
            return model_set == fixture_set  # noqa: TRY300
        except TypeError:
            return normalized_model == normalized_fixture

    return normalized_model == normalized_fixture


def _flatten_dict(d: dict[str, Any], parent_key: str = "") -> dict[str, Any]:
    """Flatten a nested dictionary for hashable comparison."""
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key).items())
        elif isinstance(v, list):
            items.append(
                (
                    new_key,
                    tuple(_normalize_value(item) if isinstance(item, dict) else item for item in v),
                )
            )
        else:
            items.append((new_key, v))
    return dict(items)


def document_differs_from_fixture[T: Document](document: T, fixture_data: dict[str, Any]) -> bool:
    """Compare a Beanie document against fixture data.

    Only compares fields present in the fixture data. Fields that exist in the
    document but not in the fixture are ignored.

    Args:
        document (T): The Beanie document from the database.
        fixture_data (dict[str, Any]): The corresponding fixture data from JSON.

    Returns:
        bool: True if the document differs from the fixture, False if they match.
    """
    for field_name, fixture_value in fixture_data.items():
        if not hasattr(document, field_name):
            continue

        if not _values_equal(getattr(document, field_name), fixture_value):
            return True

    return False


def get_differing_fields[T: Document](
    document: T, fixture_data: dict[str, Any]
) -> dict[str, tuple[Any, Any]]:
    """Get all fields that differ between a document and fixture data.

    Args:
        document (T): The Beanie document from the database.
        fixture_data (dict[str, Any]): The corresponding fixture data from JSON.

    Returns:
        dict[str, tuple[Any, Any]]: Field names mapped to (document_value, fixture_value).
    """
    differences: dict[str, tuple[Any, Any]] = {}

    for field_name, fixture_value in fixture_data.items():
        if not hasattr(document, field_name):
            continue

        document_value = getattr(document, field_name)
        if not _values_equal(document_value, fixture_value):
            differences[field_name] = (_normalize_value(document_value), fixture_value)

    return differences


class JSONWithCommentsDecoder(json.JSONDecoder):
    """JSON with comments decoder."""

    def __init__(self, **kwgs: Any):
        super().__init__(**kwgs)

    def decode(self, s: str) -> Any:  # type: ignore [override]
        """Decode the JSON with comments."""
        regex = r"""("(?:\\"|[^"])*?")|(\/\*(?:.|\s)*?\*\/|\/\/.*)"""
        s = re.sub(regex, r"\1", s)  # , flags = re.X | re.M)
        return super().decode(s)


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
        await category.save()
        created = True

    elif document_differs_from_fixture(category, fixture_category):
        differences = get_differing_fields(category, fixture_category)
        for field_name in differences:
            setattr(category, field_name, fixture_category[field_name])
        await category.save()
        updated = True

    return category, created, updated


async def _link_trait_to_advantage_category(trait: Trait) -> None:
    """Link a trait to its advantage category if specified.

    Args:
        trait (Trait): The trait to link.

    Raises:
        click.Abort: If the advantage category is not found.
    """
    if not trait.advantage_category_name:
        return

    advantage_category = await AdvantageCategory.find_one(
        AdvantageCategory.name == trait.advantage_category_name
    )
    if not advantage_category:
        msg = f"Advantage category not found: {trait.advantage_category_name}"
        logger.error(
            msg, extra={"component": "cli", "command": "_link_trait_to_advantage_category"}
        )
        raise click.Abort

    trait.advantage_category_id = advantage_category.id
    await trait.save()


async def sync_single_trait(
    fixture_trait: dict[str, Any],
    fixture_category: dict[str, Any],
    category: TraitCategory,
) -> tuple[Trait, bool, bool]:
    """Sync a single trait.

    Args:
        fixture_trait (dict[str, Any]): Fixture data for the trait.
        fixture_category (dict[str, Any]): Parent category fixture data (for default costs).
        category (TraitCategory): Parent category for the trait.

    Returns:
        tuple[Trait, bool, bool]: The trait, whether it was created, whether it was updated.
    """
    created = False
    updated = False

    # Look up by name AND parent category to handle duplicate names across categories
    trait = await Trait.find_one(
        Trait.name == fixture_trait["name"],
        Trait.parent_category_id == category.id,
        Trait.advantage_category_name == fixture_trait.get("advantage_category_name"),
    )
    if not trait:
        trait = Trait(**fixture_trait, parent_category_id=category.id)
        # Apply default costs from category if not specified
        if not fixture_trait.get("initial_cost"):
            trait.initial_cost = fixture_category.get("initial_cost", 1)
        if not fixture_trait.get("upgrade_cost"):
            trait.upgrade_cost = fixture_category.get("upgrade_cost", 1)
        if not fixture_trait.get("game_versions"):
            trait.game_versions = fixture_category.get("game_versions", [])
        if not fixture_trait.get("character_classes"):
            trait.character_classes = fixture_category.get("character_classes", [])
        await trait.save()
        created = True

        await _link_trait_to_advantage_category(trait)

    elif document_differs_from_fixture(trait, fixture_trait):
        differences = get_differing_fields(trait, fixture_trait)
        for field_name in differences:
            setattr(trait, field_name, fixture_trait[field_name])
        await trait.save()
        updated = True

    await category.save()
    return trait, created, updated


async def sync_category_traits(
    fixture_category: dict[str, Any],
    category: TraitCategory,
) -> SyncCounts:
    """Sync all traits within a category.

    Args:
        fixture_category (dict[str, Any]): Fixture data for the category.
        category (TraitCategory): The category to sync traits for.

    Returns:
        SyncCounts: Counts of created, updated, and total traits.
    """
    counts = SyncCounts()

    for fixture_trait in fixture_category.get("traits", []):
        _, created, updated = await sync_single_trait(fixture_trait, fixture_category, category)
        counts.total += 1
        if created:
            counts.created += 1
        elif updated:
            counts.updated += 1

    return counts


async def sync_section_categories(
    fixture_section: dict[str, Any],
    section: CharSheetSection,
) -> tuple[SyncCounts, SyncCounts]:
    """Sync all categories and their traits within a section.

    Args:
        fixture_section (dict[str, Any]): Fixture data for the section.
        section (CharSheetSection): The section to sync categories for.

    Returns:
        tuple[SyncCounts, SyncCounts]: Counts for categories and traits.
    """
    category_counts = SyncCounts()
    trait_counts = SyncCounts()

    for fixture_category in fixture_section.get("categories", []):
        category, created, updated = await sync_single_category(fixture_category, section)

        category_counts.total += 1
        if created:
            category_counts.created += 1
        elif updated:
            category_counts.updated += 1

        # Sync traits within this category
        traits_result = await sync_category_traits(fixture_category, category)
        trait_counts.created += traits_result.created
        trait_counts.updated += traits_result.updated
        trait_counts.total += traits_result.total

    return category_counts, trait_counts


async def create_global_dictionary_term(
    term: str, *, definition: str | None = None, link: str | None = None
) -> None:
    """Create a global dictionary term."""
    if not definition or not link:
        return

    existing_term = await DictionaryTerm.find_one(
        DictionaryTerm.term == term, DictionaryTerm.is_global == True
    )

    if existing_term:
        await existing_term.update({"definition": definition, "link": link})
        dictionary_term_counts["updated"] += 1
    else:
        await DictionaryTerm(term=term, definition=definition, link=link, is_global=True).insert()
        dictionary_term_counts["created"] += 1
