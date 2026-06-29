"""Gift trait resolution - the post-sync pass that links gifts to tribes and auspices."""

from __future__ import annotations

import json
import logging
from typing import Any

from vapi.cli.lib.comparison import FIXTURES_PATH, JSONWithCommentsDecoder, iter_trait_fixtures
from vapi.db.sql_models.character_classes import WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_sheet import Trait

logger = logging.getLogger("vapi")


def build_gift_fixture_map(
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
        with fixture_path.open() as f:
            fixture_data = json.load(f, cls=JSONWithCommentsDecoder)

    result: dict[str, dict[str, Any]] = {}
    for trait in iter_trait_fixtures(fixture_data):
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
        gift_fixture_map = build_gift_fixture_map()

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
            if trait.gift_tribe_id != tribe.pk:  # type: ignore [attr-defined] # ty:ignore[unresolved-attribute]
                # Assign the FK column named in bulk_update so the write target matches the fields list
                trait.gift_tribe_id = tribe.pk
                changed = True

        if auspice_name and auspice_name in auspices_by_name:
            auspice = auspices_by_name[auspice_name]
            auspice_gifts[auspice_name].append(trait)
            if trait.gift_auspice_id != auspice.pk:  # type: ignore [attr-defined] # ty:ignore[unresolved-attribute]
                # Assign the FK column named in bulk_update so the write target matches the fields list
                trait.gift_auspice_id = auspice.pk
                changed = True

        if changed:
            modified_traits.append(trait)

    if modified_traits:
        await Trait.bulk_update(modified_traits, fields=["gift_tribe_id", "gift_auspice_id"])

    await _populate_gift_m2m(
        tribe_gifts=tribe_gifts,
        auspice_gifts=auspice_gifts,
        tribes_by_name=tribes_by_name,
        auspices_by_name=auspices_by_name,
    )

    logger.info(
        "Resolved PostgreSQL gift trait references",
        extra={
            "num_updated": len(modified_traits),
            "component": "cli",
            "command": "seed",
        },
    )
