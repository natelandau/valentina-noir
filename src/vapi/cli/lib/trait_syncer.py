"""Trait hierarchy syncer - sections, categories, subcategories, traits."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from vapi.cli.lib.comparison import FIXTURES_PATH, JSONWithCommentsDecoder, needs_update
from vapi.cli.lib.sync_counts import SyncCounts
from vapi.db.sql_models.character_classes import WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_sheet import (
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)

logger = logging.getLogger("vapi")


@dataclass
class TraitSyncResult:
    """Aggregate sync counts for the full trait hierarchy."""

    sections: SyncCounts = field(default_factory=SyncCounts)
    categories: SyncCounts = field(default_factory=SyncCounts)
    subcategories: SyncCounts = field(default_factory=SyncCounts)
    traits: SyncCounts = field(default_factory=SyncCounts)


class TraitSyncer:
    """Sync the trait hierarchy from traits.json into PostgreSQL.

    Walks sections -> categories -> subcategories -> traits, using Tortoise
    update_or_create for upserts. Builds a gift_fixture_map for later
    gift reference resolution.
    """

    def __init__(self) -> None:
        self.result = TraitSyncResult()
        self.gift_fixture_map: dict[str, dict[str, Any]] = {}

    async def sync(self) -> None:
        """Load traits.json and sync the full hierarchy into PostgreSQL."""
        fixture_path = FIXTURES_PATH / "traits.json"
        with fixture_path.open("r") as f:
            fixture_data: list[dict[str, Any]] = json.load(f, cls=JSONWithCommentsDecoder)

        _validate_trait_value_ranges(fixture_data)

        # Pre-build gift_fixture_map before sync mutates fixture dicts via .pop()
        self.gift_fixture_map = _build_gift_fixture_map(fixture_data)

        for fixture_section in fixture_data:
            section, created, updated = await self._sync_section(fixture_section)
            if created:
                self.result.sections.created += 1
            elif updated:
                self.result.sections.updated += 1

            cat_counts, subcat_counts, trait_counts = await self._sync_section_categories(
                fixture_section, section
            )
            self.result.categories += cat_counts
            self.result.subcategories += subcat_counts
            self.result.traits += trait_counts

        self.result.sections.total = await CharSheetSection.all().count()
        self.result.categories.total = await TraitCategory.all().count()
        self.result.subcategories.total = await TraitSubcategory.all().count()
        self.result.traits.total = await Trait.filter(is_custom=False).count()

        self._log_counts()

    async def _sync_section(
        self, fixture_section: dict[str, Any]
    ) -> tuple[CharSheetSection, bool, bool]:
        """Upsert a CharSheetSection from fixture data.

        Returns:
            Tuple of (section instance, created flag, updated flag).
        """
        defaults = {
            "description": fixture_section.get("description"),
            "character_classes": fixture_section.get("character_classes", []),
            "game_versions": fixture_section.get("game_versions", []),
            "show_when_empty": fixture_section.get("show_when_empty", False),
            "order": fixture_section.get("order", 0),
        }
        section, created = await CharSheetSection.get_or_create(
            name=fixture_section["name"],
            defaults=defaults,
        )
        updated = False
        if not created and needs_update(section, defaults):
            await section.update_from_dict(defaults).save()
            updated = True
        return section, created, updated

    async def _sync_category(
        self,
        fixture_category: dict[str, Any],
        section: CharSheetSection,
    ) -> tuple[TraitCategory, bool, bool]:
        """Upsert a TraitCategory, inheriting from section when fields are absent.

        Returns:
            Tuple of (category instance, created flag, updated flag).
        """
        character_classes = fixture_category.get("character_classes") or section.character_classes
        game_versions = fixture_category.get("game_versions") or section.game_versions

        defaults = {
            "description": fixture_category.get("description"),
            "character_classes": character_classes,
            "game_versions": game_versions,
            "show_when_empty": fixture_category.get("show_when_empty", False),
            "order": fixture_category.get("order", 0),
            "initial_cost": fixture_category.get("initial_cost", 1),
            "upgrade_cost": fixture_category.get("upgrade_cost", 2),
            "count_based_cost_multiplier": fixture_category.get("count_based_cost_multiplier"),
        }
        category, created = await TraitCategory.get_or_create(
            name=fixture_category["name"],
            sheet_section=section,
            defaults=defaults,
        )
        updated = False
        if not created and needs_update(category, defaults):
            await category.update_from_dict(defaults).save()
            updated = True
        return category, created, updated

    async def _sync_subcategory(
        self,
        fixture_subcategory: dict[str, Any],
        category: TraitCategory,
        section: CharSheetSection,
    ) -> tuple[TraitSubcategory, bool, bool]:
        """Upsert a TraitSubcategory, inheriting from category when fields are absent.

        Returns:
            Tuple of (subcategory instance, created flag, updated flag).
        """
        defaults = {
            "description": fixture_subcategory.get("description"),
            "character_classes": fixture_subcategory.get("character_classes")
            or category.character_classes,
            "game_versions": fixture_subcategory.get("game_versions") or category.game_versions,
            "show_when_empty": fixture_subcategory.get("show_when_empty", True),
            "initial_cost": fixture_subcategory.get("initial_cost") or category.initial_cost,
            "upgrade_cost": fixture_subcategory.get("upgrade_cost") or category.upgrade_cost,
            "count_based_cost_multiplier": fixture_subcategory.get("count_based_cost_multiplier")
            or category.count_based_cost_multiplier,
            "requires_parent": fixture_subcategory.get("requires_parent", False),
            "pool": fixture_subcategory.get("pool"),
            "system": fixture_subcategory.get("system"),
            "hunter_edge_type": fixture_subcategory.get("hunter_edge_type"),
            "sheet_section": section,
        }
        subcategory, created = await TraitSubcategory.get_or_create(
            name=fixture_subcategory["name"],
            category=category,
            defaults=defaults,
        )
        updated = False
        if not created and needs_update(subcategory, defaults):
            await subcategory.update_from_dict(defaults).save()
            updated = True
        return subcategory, created, updated

    async def _sync_trait(
        self,
        fixture_trait: dict[str, Any],
        *,
        category: TraitCategory,
        section: CharSheetSection,
        subcategory: TraitSubcategory | None = None,
    ) -> tuple[Trait, bool, bool]:
        """Upsert a Trait, inheriting costs from subcategory/category.

        Gift attributes are extracted and stored as nullable columns on Trait.
        tribe_name/auspice_name are popped from the fixture for later resolution.

        Returns:
            Tuple of (trait instance, created flag, updated flag).
        """
        trait_name = fixture_trait["name"].strip()

        # Extract gift attributes if present
        gift_defaults: dict[str, Any] = {}
        if gift_attrs := fixture_trait.pop("gift_attributes", None):
            gift_attrs.pop("tribe_name", None)
            gift_attrs.pop("auspice_name", None)
            gift_defaults = {
                "gift_renown": gift_attrs.get("renown"),
                "gift_cost": gift_attrs.get("cost"),
                "gift_duration": gift_attrs.get("duration"),
                "gift_minimum_renown": gift_attrs.get("minimum_renown"),
                "gift_is_native": gift_attrs.get("is_native_gift", False),
            }

        # Determine inheritance source for costs
        inherit_from = subcategory or category

        defaults: dict[str, Any] = {
            "description": fixture_trait.get("description"),
            "character_classes": fixture_trait.get("character_classes")
            or (subcategory.character_classes if subcategory else category.character_classes),
            "game_versions": fixture_trait.get("game_versions")
            or (subcategory.game_versions if subcategory else category.game_versions),
            "link": fixture_trait.get("link"),
            "show_when_zero": fixture_trait.get("show_when_zero", False),
            "max_value": fixture_trait.get("max_value", 5),
            "min_value": fixture_trait.get("min_value", 0),
            "initial_cost": fixture_trait.get("initial_cost") or inherit_from.initial_cost,
            "upgrade_cost": fixture_trait.get("upgrade_cost") or inherit_from.upgrade_cost,
            "count_based_cost_multiplier": fixture_trait.get("count_based_cost_multiplier")
            or inherit_from.count_based_cost_multiplier,
            "is_rollable": fixture_trait.get("is_rollable", True),
            "pool": fixture_trait.get("pool") or (subcategory.pool if subcategory else None),
            "system": fixture_trait.get("system") or (subcategory.system if subcategory else None),
            "sheet_section": section,
            "subcategory": subcategory,
            **gift_defaults,
        }

        # Case-insensitive lookup so fixture casing variants match the signal-normalized stored name
        lookup_filter: dict[str, Any] = {"name__iexact": trait_name, "category": category}
        if subcategory:
            lookup_filter["subcategory"] = subcategory

        trait = await Trait.filter(**lookup_filter).first()
        created = False
        updated = False
        if trait is None:
            create_kwargs: dict[str, Any] = {"name": trait_name, "category": category, **defaults}
            if subcategory:
                create_kwargs["subcategory"] = subcategory
            trait = await Trait.create(**create_kwargs)
            created = True
        elif needs_update(trait, defaults):
            await trait.update_from_dict(defaults).save()
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
        """Sync all traits from a category or subcategory fixture block."""
        counts = SyncCounts()
        for fixture_trait in fixture_data.get("traits", []):
            _, created, updated = await self._sync_trait(
                fixture_trait,
                category=category,
                section=section,
                subcategory=subcategory,
            )
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
        """Sync all categories, subcategories, and traits within a section.

        Returns:
            Tuple of (category_counts, subcategory_counts, trait_counts).
        """
        cat_counts = SyncCounts()
        subcat_counts = SyncCounts()
        trait_counts = SyncCounts()

        for fixture_category in fixture_section.get("categories", []):
            category, created, updated = await self._sync_category(fixture_category, section)
            if created:
                cat_counts.created += 1
            elif updated:
                cat_counts.updated += 1

            # Sync subcategories and their traits
            for fixture_subcategory in fixture_category.get("subcategories", []):
                subcategory, sub_created, sub_updated = await self._sync_subcategory(
                    fixture_subcategory, category, section
                )
                if sub_created:
                    subcat_counts.created += 1
                elif sub_updated:
                    subcat_counts.updated += 1

                batch_counts = await self._sync_traits_batch(
                    fixture_subcategory,
                    category=category,
                    section=section,
                    subcategory=subcategory,
                )
                trait_counts += batch_counts

            # Sync category-level traits (no subcategory)
            batch_counts = await self._sync_traits_batch(
                fixture_category, category=category, section=section
            )
            trait_counts += batch_counts

        return cat_counts, subcat_counts, trait_counts

    def _log_counts(self) -> None:
        """Log sync results for each level of the hierarchy."""
        for label, counts in [
            ("character sheet sections", self.result.sections),
            ("trait categories", self.result.categories),
            ("trait subcategories", self.result.subcategories),
            ("traits", self.result.traits),
        ]:
            logger.info(
                "Bootstrapped PostgreSQL %s",
                label,
                extra={
                    "num_created": counts.created,
                    "num_updated": counts.updated,
                    "num_total": counts.total,
                    "component": "cli",
                    "command": "seed",
                },
            )


def _validate_trait_value_ranges(fixture_data: list[dict[str, Any]]) -> None:
    """Validate that no trait has min_value greater than max_value.

    Checks traits at both category and subcategory levels. Raises on the first
    batch of violations so fixture errors are caught before any database writes.

    Args:
        fixture_data: The parsed traits.json data.

    Raises:
        ValueError: If any traits have inverted min/max values.
    """
    violations: list[str] = []
    for section in fixture_data:
        for category in section.get("categories", []):
            for trait in category.get("traits", []):
                min_val = trait.get("min_value", 0)
                max_val = trait.get("max_value", 5)
                if min_val > max_val:
                    violations.append(
                        f"  {trait['name']}: min_value={min_val}, max_value={max_val}"
                    )
            for subcategory in category.get("subcategories", []):
                for trait in subcategory.get("traits", []):
                    min_val = trait.get("min_value", 0)
                    max_val = trait.get("max_value", 5)
                    if min_val > max_val:
                        violations.append(
                            f"  {trait['name']}: min_value={min_val}, max_value={max_val}"
                        )

    if violations:
        msg = "traits.json has traits where min_value > max_value:\n" + "\n".join(violations)
        raise ValueError(msg)


def _build_gift_fixture_map(
    fixture_data: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Pre-build a map of trait names to gift_attributes before sync mutates fixtures.

    Args:
        fixture_data: The parsed traits.json data. If None, reads from disk.

    Returns:
        Dict mapping lowercased trait names to their gift_attributes dicts. Callers must
        lowercase the DB trait name before lookup to match the signal-normalized storage.
    """
    if fixture_data is None:
        fixture_path = FIXTURES_PATH / "traits.json"
        with fixture_path.open("r") as f:
            fixture_data = json.load(f, cls=JSONWithCommentsDecoder)

    result: dict[str, dict[str, Any]] = {}
    for section in fixture_data:
        for category in section.get("categories", []):
            for subcategory in category.get("subcategories", []):
                for trait in subcategory.get("traits", []):
                    if ga := trait.get("gift_attributes"):
                        result[trait["name"].strip().lower()] = dict(ga)
            for trait in category.get("traits", []):
                if ga := trait.get("gift_attributes"):
                    result[trait["name"].strip().lower()] = dict(ga)
    return result


async def _populate_gift_m2m(
    tribe_gifts: dict[str, list[Trait]],
    auspice_gifts: dict[str, list[Trait]],
    tribes_by_name: dict[str, WerewolfTribe],
    auspices_by_name: dict[str, WerewolfAuspice],
) -> None:
    """Populate tribe.gifts and auspice.gifts M2M relationships."""
    for tribe_name, traits_list in tribe_gifts.items():
        if traits_list:
            tribe = tribes_by_name[tribe_name]
            await tribe.gifts.clear()
            await tribe.gifts.add(*traits_list)

    for auspice_name, traits_list in auspice_gifts.items():
        if traits_list:
            auspice = auspices_by_name[auspice_name]
            await auspice.gifts.clear()
            await auspice.gifts.add(*traits_list)


async def resolve_gift_trait_references(
    gift_fixture_map: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Resolve gift trait tribe/auspice references and build M2M links.

    After traits, tribes, and auspices are all synced, this function:
    1. Sets gift_tribe and gift_auspice FKs on gift traits
    2. Populates tribe.gifts and auspice.gifts M2M relationships

    Args:
        gift_fixture_map: Map of trait names to fixture gift_attributes. If None, reads from disk.
    """
    if gift_fixture_map is None:
        gift_fixture_map = _build_gift_fixture_map()

    # Fetch all gift traits
    gift_traits = await Trait.filter(gift_renown__isnull=False)

    # Build name -> instance maps
    tribes = await WerewolfTribe.all()
    auspices = await WerewolfAuspice.all()
    tribes_by_name = {t.name: t for t in tribes}
    auspices_by_name = {a.name: a for a in auspices}

    # Build reverse maps: tribe/auspice -> list of gift traits
    tribe_gifts: dict[str, list[Trait]] = {t.name: [] for t in tribes}
    auspice_gifts: dict[str, list[Trait]] = {a.name: [] for a in auspices}

    modified_traits: list[Trait] = []
    for trait in gift_traits:
        fixture_ga = gift_fixture_map.get(trait.name.lower())
        if not fixture_ga:
            continue

        changed = False
        tribe_name = fixture_ga.get("tribe_name")
        auspice_name = fixture_ga.get("auspice_name")

        if tribe_name and tribe_name in tribes_by_name:
            tribe = tribes_by_name[tribe_name]
            tribe_gifts[tribe_name].append(trait)
            if trait.gift_tribe_id != tribe.pk:  # type: ignore [attr-defined]
                trait.gift_tribe = tribe
                changed = True

        if auspice_name and auspice_name in auspices_by_name:
            auspice = auspices_by_name[auspice_name]
            auspice_gifts[auspice_name].append(trait)
            if trait.gift_auspice_id != auspice.pk:  # type: ignore [attr-defined]
                trait.gift_auspice = auspice
                changed = True

        if changed:
            modified_traits.append(trait)

    if modified_traits:
        await Trait.bulk_update(modified_traits, fields=["gift_tribe_id", "gift_auspice_id"])

    await _populate_gift_m2m(tribe_gifts, auspice_gifts, tribes_by_name, auspices_by_name)

    logger.info(
        "Resolved PostgreSQL gift trait references",
        extra={
            "num_updated": len(modified_traits),
            "component": "cli",
            "command": "seed",
        },
    )
