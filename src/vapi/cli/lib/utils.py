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
    CharSheetSection,
    DictionaryTerm,
    Trait,
    TraitCategory,
    TraitSubcategory,
    VampireClan,
)
from vapi.db.models.constants.trait import GiftAttributes

T = TypeVar("T", bound=Document)

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


async def sync_single_trait(  # noqa: C901, PLR0912
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
    if gift_attrs_raw is not None:
        gift_attrs_raw.pop("tribe_name", None)
        gift_attrs_raw.pop("auspice_name", None)
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
            trait.pool = subcategory.pool if subcategory else None
        if not fixture_trait.get("system"):
            trait.system = subcategory.system if subcategory else None
        await trait.save()
        created = True

    elif document_differs_from_fixture(trait, fixture_trait):
        differences = get_differing_fields(trait, fixture_trait)
        for field_name in differences:
            setattr(trait, field_name, fixture_trait[field_name])
        await trait.save()
        updated = True

    if trait.description or trait.link:
        desc = trait.description or ""
        if trait.system:
            desc += "\n## System:\n" + trait.system
        if trait.pool:
            desc += "\n## Pool:\n" + trait.pool
        await create_global_dictionary_term(
            term=trait.name,
            definition=desc,
            link=trait.link,
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
