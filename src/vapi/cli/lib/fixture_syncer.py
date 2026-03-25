"""Base fixture syncer and entity subclasses for syncing fixture files to Beanie collections."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import click
from beanie.operators import In

from vapi.cli.lib.comparison import (
    FIXTURES_PATH,
    JSONWithCommentsDecoder,
    get_differing_fields,
)
from vapi.db.models import (
    CharacterConcept,
    Trait,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)

if TYPE_CHECKING:
    from beanie import Document, PydanticObjectId

logger = logging.getLogger("vapi")


class FixtureSyncer:
    """Base for syncing a fixture file to a Beanie document collection."""

    model: type[Document]
    fixture_filename: str
    entity_label: str

    async def sync(self) -> None:
        """Load fixture, iterate items, create-or-update, and log results."""
        fixture_file = FIXTURES_PATH / self.fixture_filename
        if not fixture_file.exists():
            msg = f"Fixture file not found at path: {str(fixture_file)!r}"
            logger.error(
                msg,
                extra={
                    "component": "cli",
                    "command": f"bootstrap sync_{self.entity_label}",
                },
            )
            raise click.Abort

        with fixture_file.open("r") as file:
            fixture_items = json.load(file, cls=JSONWithCommentsDecoder)

        created = 0
        updated = 0
        for fixture_item in fixture_items:
            document = await self.model.find_one(*self._lookup_query(fixture_item))

            created_this = False
            if not document:
                document = self.model(**fixture_item)
                await document.save()
                created += 1
                created_this = True
            elif differences := get_differing_fields(document, fixture_item):
                for field_name in differences:
                    setattr(document, field_name, fixture_item[field_name])
                await document.save()
                updated += 1

            is_updated = await self._post_sync_item(document, fixture_item)
            if is_updated and not created_this:
                updated += 1

        logger.info(
            "Bootstrapped %s",
            self.entity_label,
            extra={
                "num_created": created,
                "num_updated": updated,
                "num_total": len(fixture_items),
                "component": "cli",
                "command": "bootstrap",
            },
        )

    def _lookup_query(self, fixture_item: dict[str, Any]) -> list[Any]:
        """Build find_one query. Default: match by name."""
        return [self.model.name == fixture_item["name"]]

    async def _post_sync_item(
        self,
        document: Document,  # noqa: ARG002
        fixture_item: dict[str, Any],  # noqa: ARG002
    ) -> bool:
        """Run optional hook after each item sync.

        Returns True if an additional update occurred.
        """
        return False


class VampireClanSyncer(FixtureSyncer):
    """Sync vampire clans from fixture to database."""

    model = VampireClan
    fixture_filename = "vampire_clans.json"
    entity_label = "vampire clans"

    async def _post_sync_item(self, document: Document, fixture_item: dict[str, Any]) -> bool:
        """Link disciplines to clan after sync."""
        return await self._link_disciplines_to_clan(document, fixture_item)

    async def _link_disciplines_to_clan(
        self, clan: VampireClan, fixture_clan: dict[str, Any]
    ) -> bool:
        """Link discipline traits to a vampire clan by name lookup.

        Ensures the clan's discipline_ids match the names listed in the fixture's
        disciplines_to_link field, adding missing links and removing stale ones.

        Args:
            clan: The vampire clan document to update.
            fixture_clan: The fixture data containing disciplines_to_link names.

        Returns:
            bool: True if any discipline links were changed.

        Raises:
            click.Abort: If a discipline ID on the clan references a non-existent trait.
        """
        names_to_link = fixture_clan.get("disciplines_to_link", [])
        if not names_to_link and not clan.discipline_ids:
            return False

        is_updated = False

        # Bulk fetch existing disciplines by ID
        existing_by_id: dict[PydanticObjectId, Trait] = {}
        if clan.discipline_ids:
            existing = await Trait.find(
                In(Trait.id, list(clan.discipline_ids)), Trait.is_archived == False
            ).to_list()
            existing_by_id = {t.id: t for t in existing}

            # Validate all IDs reference existing traits
            for discipline_id in clan.discipline_ids:
                if discipline_id not in existing_by_id:
                    msg = f"Trait not found: {discipline_id}"
                    logger.error(
                        msg, extra={"component": "cli", "command": "link_disciplines_to_clan"}
                    )
                    raise click.Abort

            # Remove stale links via comprehension (avoids mutation during iteration)
            new_ids = [
                did for did in clan.discipline_ids if existing_by_id[did].name in names_to_link
            ]
            if len(new_ids) != len(clan.discipline_ids):
                clan.discipline_ids = new_ids
                is_updated = True

        # Bulk fetch disciplines to add by name
        if names_to_link:
            by_name_list = await Trait.find(
                In(Trait.name, names_to_link), Trait.is_archived == False
            ).to_list()
            by_name = {t.name: t for t in by_name_list}

            for discipline_name in names_to_link:
                discipline = by_name.get(discipline_name)
                if discipline and discipline.id not in clan.discipline_ids:
                    clan.discipline_ids.append(discipline.id)
                    is_updated = True

        if is_updated:
            await clan.save()

        return is_updated


class WerewolfAuspiceSyncer(FixtureSyncer):
    """Sync werewolf auspices from fixture to database."""

    model = WerewolfAuspice
    fixture_filename = "werewolf_auspices.json"
    entity_label = "werewolf auspices"


class WerewolfTribeSyncer(FixtureSyncer):
    """Sync werewolf tribes from fixture to database."""

    model = WerewolfTribe
    fixture_filename = "werewolf_tribes.json"
    entity_label = "werewolf tribes"


class CharacterConceptSyncer(FixtureSyncer):
    """Sync character concepts from fixture to database."""

    model = CharacterConcept
    fixture_filename = "concepts.json"
    entity_label = "character concepts"
