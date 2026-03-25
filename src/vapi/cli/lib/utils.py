"""Utilities."""

import logging
from typing import Any

import click

from vapi.cli.constants import dictionary_term_counts
from vapi.cli.lib.comparison import (
    JSONWithCommentsDecoder,
    document_differs_from_fixture,
    get_differing_fields,
)
from vapi.cli.lib.trait_syncer import (
    SyncCounts,
    TraitSyncer,
    TraitSyncResult,
)
from vapi.db.models import (
    DictionaryTerm,
    Trait,
    VampireClan,
)
from vapi.db.models.constants.trait import GiftAttributes

__all__ = (
    "JSONWithCommentsDecoder",
    "SyncCounts",
    "TraitSyncResult",
    "TraitSyncer",
    "document_differs_from_fixture",
    "get_differing_fields",
    "link_disciplines_to_clan",
)

logger = logging.getLogger("vapi")


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
