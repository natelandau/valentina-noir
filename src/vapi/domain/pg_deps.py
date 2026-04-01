"""Tortoise-based dependency providers for migrated domains.

Parallel to deps.py (Beanie-based) during the migration. Once all domains
are migrated (Session 11), delete deps.py and rename this file to deps.py.
"""

from uuid import UUID

from tortoise.expressions import Q
from tortoise.models import Model

from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import (
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)
from vapi.lib.exceptions import NotFoundError


async def _find_or_404[M: Model](
    model: type[M],
    label: str,
    *extra_q: Q,
    doc_id: UUID,
    prefetch: list[str] | None = None,
) -> M:
    """Look up a record by ID and raise NotFoundError if not found.

    Automatically filters by is_archived == False.

    Args:
        model: The Tortoise Model class to query.
        label: Human-readable label for error messages.
        *extra_q: Additional Q filters beyond ID and is_archived.
        doc_id: The record UUID to look up.
        prefetch: Relations to prefetch for the returned instance.

    Raises:
        NotFoundError: If no matching record exists.
    """
    qs = model.filter(id=doc_id, is_archived=False)
    for q in extra_q:
        qs = qs.filter(q)
    if prefetch:
        qs = qs.prefetch_related(*prefetch)

    result = await qs.first()
    if not result:
        raise NotFoundError(detail=f"{label} not found")

    return result


async def provide_character_blueprint_section_by_id(
    section_id: UUID,
) -> CharSheetSection:
    """Provide a character sheet section by ID."""
    return await _find_or_404(CharSheetSection, "Character sheet section", doc_id=section_id)


async def provide_trait_category_by_id(category_id: UUID) -> TraitCategory:
    """Provide a trait category by ID."""
    return await _find_or_404(
        TraitCategory,
        "Trait category",
        doc_id=category_id,
        prefetch=["sheet_section"],
    )


async def provide_trait_subcategory_by_id(subcategory_id: UUID) -> TraitSubcategory:
    """Provide a trait subcategory by ID."""
    return await _find_or_404(
        TraitSubcategory,
        "Trait subcategory",
        doc_id=subcategory_id,
        prefetch=["category", "sheet_section"],
    )


async def provide_trait_by_id(trait_id: UUID) -> Trait:
    """Provide a trait by ID."""
    return await _find_or_404(
        Trait,
        "Trait",
        doc_id=trait_id,
        prefetch=["category", "sheet_section", "subcategory", "gift_tribe", "gift_auspice"],
    )


async def provide_character_concept_by_id(concept_id: UUID) -> CharacterConcept:
    """Provide a character concept by ID.

    Company-scoped filtering will be added when the Company model migrates to PostgreSQL.
    """
    return await _find_or_404(
        CharacterConcept,
        "Character concept",
        doc_id=concept_id,
    )


async def provide_vampire_clan_by_id(vampire_clan_id: UUID) -> VampireClan:
    """Provide a vampire clan by ID."""
    return await _find_or_404(
        VampireClan,
        "Vampire clan",
        doc_id=vampire_clan_id,
        prefetch=["disciplines"],
    )


async def provide_werewolf_tribe_by_id(werewolf_tribe_id: UUID) -> WerewolfTribe:
    """Provide a werewolf tribe by ID."""
    return await _find_or_404(
        WerewolfTribe,
        "Werewolf tribe",
        doc_id=werewolf_tribe_id,
        prefetch=["gifts"],
    )


async def provide_werewolf_auspice_by_id(
    werewolf_auspice_id: UUID,
) -> WerewolfAuspice:
    """Provide a werewolf auspice by ID."""
    return await _find_or_404(
        WerewolfAuspice,
        "Werewolf auspice",
        doc_id=werewolf_auspice_id,
        prefetch=["gifts"],
    )
