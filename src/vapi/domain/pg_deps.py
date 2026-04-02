"""Tortoise-based dependency providers for migrated domains.

Parallel to deps.py (Beanie-based) during the migration. Once all domains
are migrated (Session 11), delete deps.py and rename this file to deps.py.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from tortoise.expressions import Q
from tortoise.models import Model

from vapi.db.sql_models.campaign import Campaign as PgCampaign
from vapi.db.sql_models.campaign import CampaignBook as PgCampaignBook
from vapi.db.sql_models.campaign import CampaignChapter as PgCampaignChapter
from vapi.db.sql_models.character import Character as PgCharacter
from vapi.db.sql_models.character import CharacterInventory as PgCharacterInventory
from vapi.db.sql_models.character import CharacterTrait as PgCharacterTrait
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.company import Company as PgCompany
from vapi.db.sql_models.developer import Developer as PgDeveloper
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import User as PgUser
from vapi.domain.controllers.character.dto import CHARACTER_RESPONSE_PREFETCH

if TYPE_CHECKING:
    from litestar import Request
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import (
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)
from vapi.db.sql_models.dictionary import DictionaryTerm
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


async def provide_pg_company_by_id(company_id: UUID) -> PgCompany:
    """Provide a Tortoise Company by ID with settings prefetched."""
    return await _find_or_404(
        PgCompany,
        "Company",
        doc_id=company_id,
        prefetch=["settings"],
    )


async def provide_developer_from_request(request: "Request") -> PgDeveloper:
    """Provide the current developer from the request, queried via Tortoise.

    Read developer ID from request.user.id (set by Beanie auth middleware)
    and look up the Tortoise Developer with permissions prefetched.
    """
    developer_id = request.user.id
    result = (
        await PgDeveloper.filter(id=developer_id, is_archived=False)
        .prefetch_related("permissions__company")
        .first()
    )
    if not result:
        raise NotFoundError(detail="Developer not found")
    return result


async def provide_developer_by_id(developer_id: UUID) -> PgDeveloper:
    """Provide a Tortoise Developer by ID with permissions prefetched."""
    return await _find_or_404(
        PgDeveloper,
        "Developer",
        doc_id=developer_id,
        prefetch=["permissions__company"],
    )


async def provide_dictionary_term_by_id(
    company: PgCompany, dictionary_term_id: UUID
) -> DictionaryTerm:
    """Provide a dictionary term by ID, scoped to the requesting company.

    Returns terms owned by the company or global terms (company_id is NULL).
    """
    return await _find_or_404(
        DictionaryTerm,
        "Dictionary term",
        Q(company_id=company.id) | Q(company_id__isnull=True),
        doc_id=dictionary_term_id,
    )


async def provide_user_by_id_and_company(user_id: UUID, company: PgCompany) -> PgUser:
    """Provide a Tortoise User by ID, scoped to a company.

    Prefetches campaign_experiences for UserResponse.from_model().
    """
    return await _find_or_404(
        PgUser,
        "User",
        Q(company_id=company.id),
        doc_id=user_id,
        prefetch=["campaign_experiences"],
    )


async def provide_user_by_id(user_id: UUID) -> PgUser:
    """Provide a Tortoise User by ID with campaign experiences prefetched."""
    return await _find_or_404(
        PgUser,
        "User",
        doc_id=user_id,
        prefetch=["campaign_experiences"],
    )


async def provide_campaign_by_id(campaign_id: UUID, company: PgCompany) -> PgCampaign:
    """Provide a Tortoise Campaign by ID, scoped to a company."""
    return await _find_or_404(
        PgCampaign,
        "Campaign",
        Q(company_id=company.id),
        doc_id=campaign_id,
    )


async def provide_campaign_book_by_id(book_id: UUID, campaign: PgCampaign) -> PgCampaignBook:
    """Provide a Tortoise CampaignBook by ID, scoped to a campaign."""
    return await _find_or_404(
        PgCampaignBook,
        "Campaign book",
        Q(campaign_id=campaign.id),
        doc_id=book_id,
    )


async def provide_campaign_chapter_by_id(
    chapter_id: UUID, book: PgCampaignBook
) -> PgCampaignChapter:
    """Provide a Tortoise CampaignChapter by ID, scoped to a book."""
    return await _find_or_404(
        PgCampaignChapter,
        "Campaign chapter",
        Q(book_id=book.id),
        doc_id=chapter_id,
    )


async def provide_campaign_by_id_for_experience(campaign_id: UUID) -> PgCampaign:
    """Provide a Tortoise Campaign by ID for experience controller FK resolution."""
    return await _find_or_404(PgCampaign, "Campaign", doc_id=campaign_id)


async def provide_character_by_id_and_company(
    character_id: UUID, company: PgCompany
) -> PgCharacter:
    """Provide a Tortoise Character by ID, scoped to a company.

    Prefetches relations needed for CharacterResponse.from_model().
    """
    return await _find_or_404(
        PgCharacter,
        "Character",
        Q(company_id=company.id),
        doc_id=character_id,
        prefetch=CHARACTER_RESPONSE_PREFETCH,
    )


async def provide_inventory_item_by_id(
    inventory_item_id: UUID, character: PgCharacter
) -> PgCharacterInventory:
    """Provide a Tortoise CharacterInventory by ID, scoped to a character."""
    return await _find_or_404(
        PgCharacterInventory,
        "Inventory item",
        Q(character_id=character.id),
        doc_id=inventory_item_id,
    )


async def provide_character_trait_by_id(
    character_trait_id: UUID, character: PgCharacter
) -> PgCharacterTrait:
    """Provide a Tortoise CharacterTrait by ID, scoped to a character.

    Prefetches relations needed for CharacterTraitResponse.from_model().
    """
    from vapi.domain.controllers.character_trait.dto import CHARACTER_TRAIT_PREFETCH

    return await _find_or_404(
        PgCharacterTrait,
        "Character trait",
        Q(character_id=character.id),
        doc_id=character_trait_id,
        prefetch=CHARACTER_TRAIT_PREFETCH,
    )


async def provide_quickroll_by_id(quickroll_id: UUID) -> QuickRoll:
    """Provide a QuickRoll by ID, prefetching traits for M2M."""
    return await _find_or_404(
        QuickRoll,
        "Quick roll",
        doc_id=quickroll_id,
        prefetch=["traits"],
    )
