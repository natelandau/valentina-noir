"""Trait hierarchy syncer - sections, categories, subcategories, traits."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from vapi.cli.lib.comparison import (
    FIXTURES_PATH,
    JSONWithCommentsDecoder,
    fixture_key_error,
    iter_trait_fixtures,
    needs_update,
)
from vapi.cli.lib.gift_syncer import build_gift_fixture_map
from vapi.cli.lib.sync_counts import SyncCounts
from vapi.cli.lib.upsert import bulk_create_new, upsert
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
        # Cold-start fast path for the ~800-row traits table: when the table starts
        # empty, _sync_trait collects instances here instead of writing per row, and
        # sync() bulk-inserts them once after the walk. Sections/categories/
        # subcategories stay on the per-row path (dozens of rows, and their children
        # need the parent PKs mid-walk).
        self._traits_fast_path = False
        self._pending_traits: list[Trait] = []
        # Keys already collected, so repeated fixture rows collapse to one insert
        # exactly as the per-row (name, category, subcategory) lookup would.
        self._seen_trait_keys: set[tuple[str, Any, Any]] = set()

    async def sync(self) -> None:
        """Load traits.json and sync the full hierarchy into PostgreSQL."""
        fixture_path = FIXTURES_PATH / "traits.json"
        with fixture_path.open() as f:
            fixture_data: list[dict[str, Any]] = json.load(f, cls=JSONWithCommentsDecoder)

        _validate_trait_value_ranges(fixture_data)

        # Pre-build gift_fixture_map before sync mutates fixture dicts via .pop()
        self.gift_fixture_map = build_gift_fixture_map(fixture_data)

        self._traits_fast_path = not await Trait.all().exists()

        for fixture_section in fixture_data:
            try:
                section = await self._sync_section(fixture_section)
                await self._sync_section_categories(fixture_section, section)
            except KeyError as e:
                raise fixture_key_error(fixture_path.name, fixture_section, e) from e

        if self._pending_traits:
            await bulk_create_new(Trait, self._pending_traits, self.result.traits)

        self.result.sections.total = await CharSheetSection.all().count()
        self.result.categories.total = await TraitCategory.all().count()
        self.result.subcategories.total = await TraitSubcategory.all().count()
        self.result.traits.total = await Trait.filter(is_custom=False).count()

        self._log_counts()

    async def _sync_section(self, fixture_section: dict[str, Any]) -> CharSheetSection:
        """Upsert a CharSheetSection from fixture data."""
        defaults = {
            "description": fixture_section.get("description"),
            "character_classes": fixture_section.get("character_classes", []),
            "game_versions": fixture_section.get("game_versions", []),
            "show_when_empty": fixture_section.get("show_when_empty", False),
            "order": fixture_section.get("order", 0),
        }
        return await upsert(
            CharSheetSection,
            lookup={"name": fixture_section["name"]},
            defaults=defaults,
            counts=self.result.sections,
        )

    async def _sync_category(
        self,
        fixture_category: dict[str, Any],
        section: CharSheetSection,
    ) -> TraitCategory:
        """Upsert a TraitCategory, inheriting from section when fields are absent."""
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
        return await upsert(
            TraitCategory,
            lookup={"name": fixture_category["name"], "sheet_section": section},
            defaults=defaults,
            counts=self.result.categories,
        )

    async def _sync_subcategory(
        self,
        fixture_subcategory: dict[str, Any],
        category: TraitCategory,
        section: CharSheetSection,
    ) -> TraitSubcategory:
        """Upsert a TraitSubcategory, inheriting from category when fields are absent."""
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
        return await upsert(
            TraitSubcategory,
            lookup={"name": fixture_subcategory["name"], "category": category},
            defaults=defaults,
            counts=self.result.subcategories,
        )

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

        # Pop gift_attributes off the fixture so it is not written as a Trait column; tribe/auspice names resolve later
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

        # Cold-start: collect the instance for a single bulk INSERT after the walk.
        # Return created/updated as False so batch counting stays at zero; the final
        # bulk_create_new tallies the real create count. The dedupe key mirrors the
        # per-row lookup below (case-insensitive name within category+subcategory), so
        # a repeated fixture row collapses to one insert instead of a duplicate the
        # per-row upsert would have folded into an update.
        if self._traits_fast_path:
            trait = Trait(name=trait_name, category=category, **defaults)
            key = (trait_name.lower(), category.pk, subcategory.pk if subcategory else None)
            if key not in self._seen_trait_keys:
                self._seen_trait_keys.add(key)
                self._pending_traits.append(trait)
            return trait, False, False

        # Case-insensitive lookup so fixture casing variants match the signal-normalized stored name.
        # Constrain subcategory in both directions so a category-level trait never matches a
        # subcategory-scoped trait of the same name (and vice versa) within the category.
        lookup_filter: dict[str, Any] = {"name__iexact": trait_name, "category": category}
        if subcategory:
            lookup_filter["subcategory"] = subcategory
        else:
            lookup_filter["subcategory_id__isnull"] = True

        trait = await Trait.filter(**lookup_filter).first()
        created = False
        updated = False
        if trait is None:
            create_kwargs: dict[str, Any] = {"name": trait_name, "category": category, **defaults}
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
    ) -> None:
        """Sync all categories, subcategories, and traits within a section."""
        for fixture_category in fixture_section.get("categories", []):
            category = await self._sync_category(fixture_category, section)

            for fixture_subcategory in fixture_category.get("subcategories", []):
                subcategory = await self._sync_subcategory(fixture_subcategory, category, section)
                self.result.traits += await self._sync_traits_batch(
                    fixture_subcategory,
                    category=category,
                    section=section,
                    subcategory=subcategory,
                )

            # Category-level traits have no subcategory
            self.result.traits += await self._sync_traits_batch(
                fixture_category, category=category, section=section
            )

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
    for trait in iter_trait_fixtures(fixture_data):
        min_val = trait.get("min_value", 0)
        max_val = trait.get("max_value", 5)
        if min_val > max_val:
            violations.append(f"  {trait['name']}: min_value={min_val}, max_value={max_val}")

    if violations:
        msg = "traits.json has traits where min_value > max_value:\n" + "\n".join(violations)
        raise ValueError(msg)
