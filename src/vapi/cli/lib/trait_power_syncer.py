"""Trait power syncer - per-dot-level powers attached to traits."""

from __future__ import annotations

import json
import logging
from typing import Any

from vapi.cli.lib.comparison import FIXTURES_PATH, JSONWithCommentsDecoder
from vapi.cli.lib.sync_counts import SyncCounts
from vapi.cli.lib.upsert import upsert
from vapi.db.sql_models.character_sheet import Trait, TraitPower

logger = logging.getLogger("vapi")


class TraitPowerSyncer:
    """Sync trait powers from trait_powers.json into PostgreSQL.

    Each fixture entry names a parent trait by (name, category[, subcategory]);
    its powers are upserted keyed on (trait, level). An unresolved trait is a
    fixture error and raises rather than being skipped.
    """

    fixture_filename = "trait_powers.json"

    def __init__(self) -> None:
        self.counts = SyncCounts()
        self.fixture_entries: list[dict[str, Any]] = []

    async def sync(self) -> None:
        """Load trait_powers.json and upsert every power."""
        fixture_path = FIXTURES_PATH / self.fixture_filename
        with fixture_path.open() as f:
            self.fixture_entries = json.load(f, cls=JSONWithCommentsDecoder)
        await self.sync_entries()

    async def sync_entries(self) -> None:
        """Resolve each entry's trait and upsert its powers. Kept separate from file IO for testing."""
        for entry in self.fixture_entries:
            trait = await self._resolve_trait(entry)
            for fixture_power in entry.get("powers", []):
                await upsert(
                    TraitPower,
                    lookup={"trait": trait, "level": fixture_power["level"]},
                    defaults={
                        "name": fixture_power["name"],
                        "description": fixture_power.get("description"),
                        "system": fixture_power.get("system"),
                        "link": fixture_power.get("link"),
                    },
                    counts=self.counts,
                )

        self.counts.total = await TraitPower.all().count()
        self._log_counts()

    async def _resolve_trait(self, entry: dict[str, Any]) -> Trait:
        """Resolve the parent trait by name, category, and optional subcategory."""
        lookup: dict[str, Any] = {
            "name__iexact": entry["trait"].strip(),
            "category__name": entry["category"],
        }
        if subcategory := entry.get("subcategory"):
            lookup["subcategory__name"] = subcategory
        else:
            lookup["subcategory_id__isnull"] = True

        trait = await Trait.filter(**lookup).first()
        if trait is None:
            msg = (
                f"trait_powers.json references trait {entry['trait']!r} in category "
                f"{entry['category']!r} (subcategory {entry.get('subcategory')!r}) which does not exist"
            )
            raise ValueError(msg)
        return trait

    def _log_counts(self) -> None:
        """Log sync results."""
        logger.info(
            "Bootstrapped PostgreSQL trait powers",
            extra={
                "num_created": self.counts.created,
                "num_updated": self.counts.updated,
                "num_total": self.counts.total,
                "component": "cli",
                "command": "seed",
            },
        )
