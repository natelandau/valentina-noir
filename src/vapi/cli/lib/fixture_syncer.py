"""Fixture syncer base class and simple subclasses."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tortoise.models import Model

from vapi.cli.lib.comparison import FIXTURES_PATH, JSONWithCommentsDecoder, needs_update
from vapi.cli.lib.sync_counts import SyncCounts
from vapi.constants import WerewolfRenown
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import Trait

logger = logging.getLogger("vapi")


class FixtureSyncer:
    """Base class for syncing fixture JSON data into PostgreSQL via Tortoise ORM.

    Subclasses define the model, fixture filename, entity label, and how to
    extract lookup fields and defaults from each fixture item.
    """

    model: type[Model]  # Tortoise Model class
    fixture_filename: str  # JSON filename in db/fixtures/
    entity_label: str  # Human label for logging

    def __init__(self) -> None:
        self.counts = SyncCounts()

    async def sync(self) -> None:
        """Load fixture data and upsert all items into PostgreSQL."""
        fixture_path = FIXTURES_PATH / self.fixture_filename
        with fixture_path.open("r") as f:
            fixture_items: list[dict[str, Any]] = json.load(f, cls=JSONWithCommentsDecoder)

        for fixture_item in fixture_items:
            lookup = self._lookup_fields(fixture_item)
            defaults = self._defaults(fixture_item)
            instance, created = await self.model.get_or_create(defaults=defaults, **lookup)
            if created:
                self.counts.created += 1
            elif needs_update(instance, defaults):
                await instance.update_from_dict(defaults).save()
                self.counts.updated += 1
            self._process_item(fixture_item, instance)

        await self._post_sync()
        self.counts.total = await self.model.all().count()
        self._log_counts()

    def _lookup_fields(self, fixture_item: dict[str, Any]) -> dict[str, Any]:
        """Return the fields used to look up an existing record."""
        return {"name": fixture_item["name"]}

    def _defaults(self, fixture_item: dict[str, Any]) -> dict[str, Any]:
        """Return the fields to set/update on the record."""
        raise NotImplementedError

    def _process_item(self, fixture_item: dict[str, Any], instance: Any) -> None:
        """Hook called after each item is upserted. Default is no-op."""

    async def _post_sync(self) -> None:
        """Hook for post-sync operations. Default is no-op."""

    def _log_counts(self) -> None:
        """Log sync results."""
        logger.info(
            "Bootstrapped PostgreSQL %s",
            self.entity_label,
            extra={
                "num_created": self.counts.created,
                "num_updated": self.counts.updated,
                "num_total": self.counts.total,
                "component": "cli",
                "command": "seed",
            },
        )


class WerewolfAuspiceSyncer(FixtureSyncer):
    """Sync werewolf auspices from fixture into PostgreSQL."""

    model = WerewolfAuspice
    fixture_filename = "werewolf_auspices.json"
    entity_label = "werewolf auspices"

    def _defaults(self, fixture_item: dict[str, Any]) -> dict[str, Any]:
        """Return auspice fields to set/update."""
        return {
            "description": fixture_item.get("description"),
            "game_versions": fixture_item.get("game_versions", []),
            "link": fixture_item.get("link"),
        }


class WerewolfTribeSyncer(FixtureSyncer):
    """Sync werewolf tribes from fixture into PostgreSQL."""

    model = WerewolfTribe
    fixture_filename = "werewolf_tribes.json"
    entity_label = "werewolf tribes"

    def _defaults(self, fixture_item: dict[str, Any]) -> dict[str, Any]:
        """Return tribe fields to set/update."""
        return {
            "description": fixture_item.get("description"),
            "game_versions": fixture_item.get("game_versions", []),
            "renown": WerewolfRenown(fixture_item["renown"]),
            "patron_spirit": fixture_item.get("patron_spirit"),
            "favor": fixture_item.get("favor"),
            "ban": fixture_item.get("ban"),
            "link": fixture_item.get("link"),
        }


class CharacterConceptSyncer(FixtureSyncer):
    """Sync character concepts from fixture into PostgreSQL."""

    model = CharacterConcept
    fixture_filename = "concepts.json"
    entity_label = "character concepts"

    def _defaults(self, fixture_item: dict[str, Any]) -> dict[str, Any]:
        """Return concept fields to set/update."""
        return {
            "description": fixture_item["description"],
            "examples": fixture_item.get("examples", []),
            "max_specialties": fixture_item.get("max_specialties", 0),
            "specialties": fixture_item.get("specialties", []),
            "favored_ability_names": fixture_item.get("favored_ability_names", []),
        }


class VampireClanSyncer(FixtureSyncer):
    """Sync vampire clans from fixture into PostgreSQL, then link discipline M2M."""

    model = VampireClan
    fixture_filename = "vampire_clans.json"
    entity_label = "vampire clans"

    def __init__(self) -> None:
        super().__init__()
        self._discipline_links: list[tuple[VampireClan, list[str]]] = []

    def _defaults(self, fixture_item: dict[str, Any]) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "description": fixture_item.get("description"),
            "game_versions": fixture_item.get("game_versions", []),
            "link": fixture_item.get("link"),
        }
        if bane := fixture_item.get("bane"):
            defaults["bane_name"] = bane["name"]
            defaults["bane_description"] = bane["description"]
        if variant_bane := fixture_item.get("variant_bane"):
            defaults["variant_bane_name"] = variant_bane["name"]
            defaults["variant_bane_description"] = variant_bane["description"]
        if compulsion := fixture_item.get("compulsion"):
            defaults["compulsion_name"] = compulsion["name"]
            defaults["compulsion_description"] = compulsion["description"]
        return defaults

    def _process_item(self, fixture_item: dict[str, Any], instance: Any) -> None:
        """Collect discipline link data for post-sync M2M linking."""
        if disciplines := fixture_item.get("disciplines_to_link"):
            self._discipline_links.append((instance, disciplines))

    async def _post_sync(self) -> None:
        """Link discipline traits to clans via M2M relationship."""
        if not self._discipline_links:
            return

        all_names = {name for _, names in self._discipline_links for name in names}
        traits_by_name = {t.name: t for t in await Trait.filter(name__in=all_names)}

        for clan, discipline_names in self._discipline_links:
            await clan.disciplines.clear()
            traits = [traits_by_name[n] for n in discipline_names if n in traits_by_name]
            await clan.disciplines.add(*traits)
