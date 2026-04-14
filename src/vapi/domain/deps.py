"""Dependency providers for Litestar route handlers.

Each provider resolves a Tortoise ORM model instance from request parameters
(path IDs, auth context) and raises NotFoundError when the resource does not exist.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from tortoise.expressions import Q
from tortoise.models import Model

from vapi.constants import ON_BEHALF_OF_HEADER_KEY
from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.character import Character, CharacterInventory, CharacterTrait
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import (
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.developer import Developer
from vapi.db.sql_models.diceroll import DiceRoll
from vapi.db.sql_models.dictionary import DictionaryTerm
from vapi.db.sql_models.notes import Note
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import User
from vapi.domain.controllers.character.dto import CHARACTER_RESPONSE_PREFETCH
from vapi.lib.exceptions import NotFoundError, ValidationError

if TYPE_CHECKING:
    from litestar import Request


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
    """Provide a character concept by ID."""
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


async def provide_company_by_id(company_id: UUID) -> Company:
    """Provide a Company by ID with settings prefetched."""
    return await _find_or_404(
        Company,
        "Company",
        doc_id=company_id,
        prefetch=["settings"],
    )


async def provide_developer_from_request(request: "Request") -> Developer:
    """Provide the current developer from the request.

    Read developer ID from request.user.id (set by auth middleware)
    and look up the Developer with permissions prefetched.
    """
    developer_id = request.user.id
    result = (
        await Developer.filter(id=developer_id, is_archived=False)
        .prefetch_related("permissions__company")
        .first()
    )
    if not result:
        raise NotFoundError(detail="Developer not found")
    return result


async def provide_developer_by_id(developer_id: UUID) -> Developer:
    """Provide a Developer by ID with permissions prefetched."""
    return await _find_or_404(
        Developer,
        "Developer",
        doc_id=developer_id,
        prefetch=["permissions__company"],
    )


async def provide_dictionary_term_by_id(
    company: Company, dictionary_term_id: UUID
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


async def provide_target_user(user_id: UUID, company: Company) -> User:
    """Resolve user_id from the path — the user being acted on.

    Only used by User domain controllers where user_id is in the URL path
    identifying the target resource. Prefetches campaign_experiences for
    UserResponse.from_model().
    """
    return await _find_or_404(
        User,
        "User",
        Q(company_id=company.id),
        doc_id=user_id,
        prefetch=["campaign_experiences"],
    )


async def provide_acting_user(request: "Request", company: Company) -> User:
    """Resolve the On-Behalf-Of header to a User within the given company.

    Check request.state.acting_user first (stashed by guards to avoid duplicate
    queries). If not cached, read the On-Behalf-Of header, validate it, load
    the user scoped to the company, and stash the result on request.state.

    Args:
        request: The Litestar request object.
        company: The company resolved from the path.

    Raises:
        ValidationError: If the header is missing or not a valid UUID.
        NotFoundError: If the user does not exist, is archived, or is not in the company.
    """
    cached: User | None = getattr(request.state, "acting_user", None)
    if cached is not None:
        return cached

    header_value = request.headers.get(ON_BEHALF_OF_HEADER_KEY)
    if not header_value:
        raise ValidationError(
            detail=f"{ON_BEHALF_OF_HEADER_KEY} header is required",
            invalid_parameters=[
                {"field": ON_BEHALF_OF_HEADER_KEY, "message": "Header is required"},
            ],
        )

    try:
        user_id = UUID(header_value)
    except ValueError as e:
        raise ValidationError(
            detail=f"{ON_BEHALF_OF_HEADER_KEY} header must be a valid UUID",
            invalid_parameters=[
                {"field": ON_BEHALF_OF_HEADER_KEY, "message": "Must be a valid UUID"},
            ],
        ) from e

    user = (
        await User.filter(
            id=user_id,
            company_id=company.id,
            is_archived=False,
        )
        .prefetch_related("campaign_experiences")
        .first()
    )

    if not user:
        raise NotFoundError(detail="Acting user not found")

    request.state.acting_user = user
    return user


async def provide_user_by_id(user_id: UUID) -> User:
    """Provide a User by ID with campaign experiences prefetched."""
    return await _find_or_404(
        User,
        "User",
        doc_id=user_id,
        prefetch=["campaign_experiences"],
    )


async def provide_campaign_by_id(campaign_id: UUID, company: Company) -> Campaign:
    """Provide a Campaign by ID, scoped to a company."""
    return await _find_or_404(
        Campaign,
        "Campaign",
        Q(company_id=company.id),
        doc_id=campaign_id,
    )


async def provide_campaign_book_by_id(book_id: UUID, campaign: Campaign) -> CampaignBook:
    """Provide a CampaignBook by ID, scoped to a campaign."""
    return await _find_or_404(
        CampaignBook,
        "Campaign book",
        Q(campaign_id=campaign.id),
        doc_id=book_id,
    )


async def provide_campaign_chapter_by_id(chapter_id: UUID, book: CampaignBook) -> CampaignChapter:
    """Provide a CampaignChapter by ID, scoped to a book."""
    return await _find_or_404(
        CampaignChapter,
        "Campaign chapter",
        Q(book_id=book.id),
        doc_id=chapter_id,
    )


async def provide_campaign_by_id_for_experience(campaign_id: UUID) -> Campaign:
    """Provide a Campaign by ID for experience controller FK resolution."""
    return await _find_or_404(Campaign, "Campaign", doc_id=campaign_id)


async def provide_character_by_id_and_company(character_id: UUID, company: Company) -> Character:
    """Provide a Character by ID, scoped to a company.

    Prefetches relations needed for CharacterResponse.from_model().
    """
    return await _find_or_404(
        Character,
        "Character",
        Q(company_id=company.id),
        doc_id=character_id,
        prefetch=CHARACTER_RESPONSE_PREFETCH,
    )


async def provide_inventory_item_by_id(
    inventory_item_id: UUID, character: Character
) -> CharacterInventory:
    """Provide a CharacterInventory by ID, scoped to a character."""
    return await _find_or_404(
        CharacterInventory,
        "Inventory item",
        Q(character_id=character.id),
        doc_id=inventory_item_id,
    )


async def provide_character_trait_by_id(
    character_trait_id: UUID, character: Character
) -> CharacterTrait:
    """Provide a CharacterTrait by ID, scoped to a character.

    Prefetches relations needed for CharacterTraitResponse.from_model().
    """
    from vapi.domain.controllers.character_trait.dto import CHARACTER_TRAIT_PREFETCH

    return await _find_or_404(
        CharacterTrait,
        "Character trait",
        Q(character_id=character.id),
        doc_id=character_trait_id,
        prefetch=CHARACTER_TRAIT_PREFETCH,
    )


async def provide_note_by_id(note_id: UUID) -> Note:
    """Provide a Note by ID."""
    return await _find_or_404(Note, "Note", doc_id=note_id)


async def provide_quickroll_by_id(quickroll_id: UUID) -> QuickRoll:
    """Provide a QuickRoll by ID, prefetching traits for M2M."""
    return await _find_or_404(
        QuickRoll,
        "Quick roll",
        doc_id=quickroll_id,
        prefetch=["traits"],
    )


async def provide_diceroll_by_id(diceroll_id: UUID) -> DiceRoll:
    """Provide a DiceRoll by ID, prefetching result and traits."""
    return await _find_or_404(
        DiceRoll,
        "Dice roll",
        doc_id=diceroll_id,
        prefetch=["roll_result", "traits"],
    )


async def provide_s3_asset_by_id(asset_id: UUID) -> S3Asset:
    """Provide an S3Asset by ID."""
    return await _find_or_404(S3Asset, "Asset", doc_id=asset_id)
