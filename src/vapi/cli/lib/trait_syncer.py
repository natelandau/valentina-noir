"""Trait hierarchy sync logic.

Encapsulates the section -> category -> subcategory -> trait sync pipeline
that loads traits from the JSON fixture and upserts them into MongoDB.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self

import click

from vapi.cli.lib.comparison import (
    FIXTURES_PATH,
    JSONWithCommentsDecoder,
    get_differing_fields,
)
from vapi.db.models import (
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
    WerewolfAuspice,
    WerewolfTribe,
)
from vapi.db.models.constants.trait import GiftAttributes

if TYPE_CHECKING:
    from beanie import PydanticObjectId

__all__ = (
    "SyncCounts",
    "TraitSyncResult",
    "TraitSyncer",
    "resolve_gift_trait_references",
)

logger = logging.getLogger("vapi")


@dataclass
class SyncCounts:
    """Track counts for sync operations."""

    created: int = 0
    updated: int = 0
    total: int = 0

    def __iadd__(self, other: SyncCounts) -> Self:
        """Accumulate counts from another SyncCounts instance."""
        self.created += other.created
        self.updated += other.updated
        self.total += other.total
        return self


@dataclass
class TraitSyncResult:
    """Result of syncing traits fixture."""

    sections: SyncCounts = field(default_factory=SyncCounts)
    categories: SyncCounts = field(default_factory=SyncCounts)
    subcategories: SyncCounts = field(default_factory=SyncCounts)
    traits: SyncCounts = field(default_factory=SyncCounts)


class TraitSyncer:
    """Synchronize the trait hierarchy from the JSON fixture into the database."""

    def __init__(self) -> None:
        self.result = TraitSyncResult()
        self.gift_fixture_map: dict[str, dict] = {}

    async def sync(self) -> None:
        """Load the traits fixture and sync all sections, categories, and traits.

        This is the public entry point. It loads sections, categories, and traits
        from the traits.json fixture and synchronizes them with the database,
        creating new entities or updating existing ones as needed.
        """
        fixture_file = FIXTURES_PATH / "traits.json"
        if not fixture_file.exists():
            msg = f"Fixture file not found at path: {str(fixture_file)!r}"
            logger.error(msg, extra={"component": "cli", "command": "bootstrap sync_traits"})
            raise click.Abort

        with fixture_file.open("r") as file:
            fixture_traits = json.load(file, cls=JSONWithCommentsDecoder)

        # Build gift map before sync loop because _sync_trait mutates fixture dicts via .pop()
        self.gift_fixture_map = _build_gift_fixture_map(fixture_traits)

        for fixture_section in fixture_traits:
            section, created, updated = await self._sync_section(fixture_section)
            self.result.sections.total += 1
            if created:
                self.result.sections.created += 1
            elif updated:
                self.result.sections.updated += 1

            category_counts, subcategory_counts, trait_counts = await self._sync_section_categories(
                fixture_section, section
            )
            self.result.categories += category_counts
            self.result.subcategories += subcategory_counts
            self.result.traits += trait_counts

        logger.info(
            "Bootstrapped character sheet sections",
            extra={
                "num_created": self.result.sections.created,
                "num_updated": self.result.sections.updated,
                "num_total": self.result.sections.total,
                "component": "cli",
                "command": "bootstrap",
            },
        )
        logger.info(
            "Bootstrapped Trait categories",
            extra={
                "num_created": self.result.categories.created,
                "num_updated": self.result.categories.updated,
                "num_total": self.result.categories.total,
                "component": "cli",
                "command": "bootstrap",
            },
        )
        logger.info(
            "Bootstrapped Trait subcategories",
            extra={
                "num_created": self.result.subcategories.created,
                "num_updated": self.result.subcategories.updated,
                "num_total": self.result.subcategories.total,
                "component": "cli",
                "command": "bootstrap",
            },
        )
        logger.info(
            "Bootstrapped Traits",
            extra={
                "num_created": self.result.traits.created,
                "num_updated": self.result.traits.updated,
                "num_total": self.result.traits.total,
                "component": "cli",
                "command": "bootstrap",
            },
        )

    async def _sync_section(
        self,
        fixture_section: dict[str, Any],
    ) -> tuple[CharSheetSection, bool, bool]:
        """Sync a single character sheet section.

        Args:
            fixture_section: Fixture data for the section.

        Returns:
            tuple[CharSheetSection, bool, bool]: The section, whether it was created,
                whether it was updated.
        """
        created = False
        updated = False

        section = await CharSheetSection.find_one(CharSheetSection.name == fixture_section["name"])
        if not section:
            section = CharSheetSection(**fixture_section)
            await section.save()
            created = True
        elif differences := get_differing_fields(section, fixture_section):
            for field_name in differences:
                setattr(section, field_name, fixture_section[field_name])
            await section.save()
            updated = True

        return section, created, updated

    async def _sync_category(
        self,
        fixture_category: dict[str, Any],
        section: CharSheetSection,
    ) -> tuple[TraitCategory, bool, bool]:
        """Sync a single trait category.

        Args:
            fixture_category: Fixture data for the category.
            section: Parent section for the category.

        Returns:
            tuple[TraitCategory, bool, bool]: The category, whether it was created,
                whether it was updated.
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

        elif differences := get_differing_fields(category, fixture_category):
            for field_name in differences:
                setattr(category, field_name, fixture_category[field_name])
            await category.save()
            updated = True

        return category, created, updated

    async def _sync_subcategory(
        self,
        fixture_subcategory: dict[str, Any],
        category: TraitCategory,
    ) -> tuple[TraitSubcategory, bool, bool]:
        """Sync a single trait subcategory.

        Inherits initial_cost, upgrade_cost, game_versions, and character_classes
        from the parent category when not specified in the fixture.

        Args:
            fixture_subcategory: Fixture data for the subcategory.
            category: Parent category for the subcategory.

        Returns:
            tuple[TraitSubcategory, bool, bool]: The subcategory, whether it was created,
                whether it was updated.
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

        elif differences := get_differing_fields(subcategory, fixture_subcategory):
            for field_name in differences:
                setattr(subcategory, field_name, fixture_subcategory[field_name])
            await subcategory.save()
            updated = True

        return subcategory, created, updated

    async def _sync_trait(  # noqa: C901
        self,
        fixture_trait: dict[str, Any],
        *,
        category: TraitCategory,
        section: CharSheetSection,
        subcategory: TraitSubcategory | None = None,
    ) -> tuple[Trait, bool, bool]:
        """Sync a single trait.

        Inherits default costs, game versions, character classes, pool, and system
        from the parent subcategory or category when not specified in the fixture.

        Args:
            fixture_trait: Fixture data for the trait.
            category: Parent category for the trait.
            section: Parent section for the trait.
            subcategory: Optional parent subcategory for the trait.

        Returns:
            tuple[Trait, bool, bool]: The trait, whether it was created, whether it was updated.
        """
        created = False
        updated = False

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
                    subcategory.character_classes
                    if subcategory
                    else category.character_classes or []
                )
            if not fixture_trait.get("pool"):
                trait.pool = subcategory.pool if subcategory and subcategory.pool else None
            if not fixture_trait.get("system"):
                trait.system = subcategory.system if subcategory and subcategory.system else None
            await trait.save()
            created = True

        elif differences := get_differing_fields(trait, fixture_trait):
            for field_name in differences:
                setattr(trait, field_name, fixture_trait[field_name])
            await trait.save()
            updated = True

        return trait, created, updated

    async def _sync_traits_batch(
        self,
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
            _, created, updated = await self._sync_trait(
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

    async def _sync_section_categories(
        self,
        fixture_section: dict[str, Any],
        section: CharSheetSection,
    ) -> tuple[SyncCounts, SyncCounts, SyncCounts]:
        """Sync all categories and their traits within a section.

        Args:
            fixture_section: Fixture data for the section.
            section: The section to sync categories for.

        Returns:
            tuple[SyncCounts, SyncCounts, SyncCounts]: Counts for categories,
                subcategories, and traits.
        """
        category_counts = SyncCounts()
        subcategory_counts = SyncCounts()
        trait_counts = SyncCounts()

        for fixture_category in fixture_section.get("categories", []):
            category, created, updated = await self._sync_category(fixture_category, section)

            category_counts.total += 1
            if created:
                category_counts.created += 1
            elif updated:
                category_counts.updated += 1

            for fixture_subcategory in fixture_category.get("subcategories", []):
                subcategory, created, updated = await self._sync_subcategory(
                    fixture_subcategory, category
                )
                subcategory_counts.total += 1
                if created:
                    subcategory_counts.created += 1
                elif updated:
                    subcategory_counts.updated += 1

                subcategory_traits_result = await self._sync_traits_batch(
                    fixture_subcategory,
                    subcategory=subcategory,
                    category=category,
                    section=section,
                )
                trait_counts += subcategory_traits_result

            traits_result = await self._sync_traits_batch(
                fixture_category, category=category, section=section
            )
            trait_counts += traits_result

        return category_counts, subcategory_counts, trait_counts


async def resolve_gift_trait_references(
    gift_fixture_map: dict[str, dict] | None = None,
) -> None:
    """Resolve tribe_name/auspice_name to tribe_id/auspice_id on gift traits.

    Run after werewolf tribes and auspices are synced so the documents
    exist for lookup. During initial trait sync the tribe/auspice IDs
    are left as None because those documents don't exist yet.

    Args:
        gift_fixture_map: Pre-built mapping of gift trait names to fixture gift_attributes.
            If None, reads and parses traits.json from disk.
    """
    if gift_fixture_map is None:
        gift_fixture_map = _build_gift_fixture_map()
    gift_traits = await Trait.find(Trait.gift_attributes != None).to_list()

    tribes = await WerewolfTribe.find().to_list()
    auspices = await WerewolfAuspice.find().to_list()
    tribes_by_name = {t.name: t.id for t in tribes}
    auspices_by_name = {a.name: a.id for a in auspices}

    updated = 0
    for trait in gift_traits:
        fixture_ga = gift_fixture_map.get(trait.name)
        if not fixture_ga:
            continue

        changed = _resolve_single_gift_references(
            trait, fixture_ga, tribes_by_name, auspices_by_name
        )
        if changed:
            await trait.save()
            updated += 1

    tribe_gift_map: dict[PydanticObjectId, list[PydanticObjectId]] = {}
    auspice_gift_map: dict[PydanticObjectId, list[PydanticObjectId]] = {}
    for trait in gift_traits:
        attrs = trait.gift_attributes
        if attrs and attrs.tribe_id:
            tribe_gift_map.setdefault(attrs.tribe_id, []).append(trait.id)
        if attrs and attrs.auspice_id:
            auspice_gift_map.setdefault(attrs.auspice_id, []).append(trait.id)

    for tribe in tribes:
        tribe.gift_trait_ids = tribe_gift_map.get(tribe.id, [])
        await tribe.save()

    for auspice in auspices:
        auspice.gift_trait_ids = auspice_gift_map.get(auspice.id, [])
        await auspice.save()

    logger.info(
        "Resolved gift trait tribe/auspice references",
        extra={
            "num_updated": updated,
            "num_total": len(gift_traits),
            "component": "cli",
            "command": "bootstrap",
        },
    )


def _build_gift_fixture_map(
    fixture_data: list[dict[str, Any]] | None = None,
) -> dict[str, dict]:
    """Build a mapping of gift trait name to fixture gift_attributes dict.

    Args:
        fixture_data: Pre-parsed traits.json sections. If None, reads from disk.
    """
    if fixture_data is None:
        fixture_file = FIXTURES_PATH / "traits.json"
        with fixture_file.open("r") as file:
            fixture_data = json.load(file, cls=JSONWithCommentsDecoder)

    result: dict[str, dict] = {}
    for section in fixture_data:
        for cat in section.get("categories", []):
            if cat.get("name") == "Gifts":
                for t in cat.get("traits", []):
                    if "gift_attributes" in t:
                        # Copy to avoid mutation by _sync_trait's .pop() calls
                        result[t["name"].strip().title()] = dict(t["gift_attributes"])
    return result


def _resolve_single_gift_references(
    trait: Trait,
    fixture_ga: dict,
    tribes_by_name: dict[str, PydanticObjectId],
    auspices_by_name: dict[str, PydanticObjectId],
) -> bool:
    """Resolve tribe/auspice names to IDs on a single gift trait."""
    attrs = trait.gift_attributes
    changed = False

    tribe_name = fixture_ga.get("tribe_name")
    if tribe_name and attrs.tribe_id is None:
        tribe_id = tribes_by_name.get(tribe_name)
        if tribe_id:
            attrs.tribe_id = tribe_id
            changed = True

    auspice_name = fixture_ga.get("auspice_name")
    if auspice_name and attrs.auspice_id is None:
        auspice_id = auspices_by_name.get(auspice_name)
        if auspice_id:
            attrs.auspice_id = auspice_id
            changed = True

    return changed
