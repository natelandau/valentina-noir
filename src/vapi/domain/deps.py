"""Domain dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from beanie import Document, PydanticObjectId
from litestar.params import Parameter

from vapi.db.models import (
    Campaign,
    CampaignBook,
    CampaignChapter,
    Character,
    CharacterInventory,
    CharacterTrait,
    Company,
    Developer,
    Note,
    QuickRoll,
    S3Asset,
    Trait,
    TraitCategory,
    User,
)
from vapi.db.models.base import BaseDocument
from vapi.lib.exceptions import NotFoundError

if TYPE_CHECKING:
    from litestar import Request


async def _find_or_404[T: Document](
    model: type[T],
    label: str,
    *extra_filters: object,
    doc_id: PydanticObjectId,
    fetch_links: bool = False,
) -> T:
    """Look up a document by ID and raise NotFoundError if not found.

    Automatically filters by is_archived == False for BaseDocument subclasses.

    Args:
        model: The Beanie Document class to query.
        label: Human-readable label for error messages.
        *extra_filters: Additional query filters beyond ID and is_archived.
        doc_id: The document ID to look up.
        fetch_links: Whether to fetch linked documents.

    Returns:
        The found document.

    Raises:
        NotFoundError: If no matching document exists.
    """
    filters: list = [model.id == doc_id]

    if issubclass(model, BaseDocument):
        filters.append(model.is_archived == False)

    filters.extend(extra_filters)

    result = await model.find_one(*filters, fetch_links=fetch_links)
    if not result:
        raise NotFoundError(detail=f"{label} not found")

    return result


async def provide_s3_asset_by_id(asset_id: PydanticObjectId) -> S3Asset:
    """Provide an S3 asset by ID."""
    return await _find_or_404(S3Asset, "S3 asset", doc_id=asset_id)


async def provide_developer_from_request(request: Request) -> Developer:
    """Provide a Developer object from the request."""
    return await _find_or_404(Developer, "User", doc_id=request.user.id)


async def provide_developer_by_id(
    developer_id: Annotated[
        PydanticObjectId, Parameter(title="Developer ID", description="The user to act on.")
    ],
) -> Developer:
    """Provide a Developer by ID."""
    return await _find_or_404(Developer, "User", doc_id=developer_id)


async def provide_campaign_by_id(campaign_id: PydanticObjectId, company: Company) -> Campaign:
    """Provide a campaign by ID."""
    return await _find_or_404(
        Campaign, "Campaign", Campaign.company_id == company.id, doc_id=campaign_id
    )


async def provide_campaign_book_by_id(
    book_id: PydanticObjectId, campaign: Campaign
) -> CampaignBook:
    """Provide a campaign book by ID."""
    return await _find_or_404(
        CampaignBook, "Campaign book", CampaignBook.campaign_id == campaign.id, doc_id=book_id
    )


async def provide_campaign_chapter_by_id(
    chapter_id: PydanticObjectId, book: CampaignBook
) -> CampaignChapter:
    """Provide a campaign chapter by ID."""
    return await _find_or_404(
        CampaignChapter,
        "Campaign chapter",
        CampaignChapter.book_id == book.id,
        doc_id=chapter_id,
    )


async def provide_company_by_id(
    company_id: Annotated[
        PydanticObjectId, Parameter(title="Company ID", description="The company to act on.")
    ],
) -> Company:
    """Provide a company by ID."""
    return await _find_or_404(Company, "Company", doc_id=company_id)


async def provide_character_by_id_and_company(
    character_id: PydanticObjectId, company: Company
) -> Character:
    """Provide a character by ID."""
    return await _find_or_404(
        Character, "Character", Character.company_id == company.id, doc_id=character_id
    )


async def provide_character_trait_by_id(
    character_trait_id: PydanticObjectId, character_id: PydanticObjectId
) -> CharacterTrait:
    """Provide a character trait by ID or trait ID."""
    character_trait = await CharacterTrait.find_one(
        CharacterTrait.id == character_trait_id,
        fetch_links=True,
    )

    if not character_trait:
        trait = await Trait.get(character_trait_id)
        if not trait:
            raise NotFoundError(detail="Character trait not found")
        character_trait = await CharacterTrait.find_one(
            CharacterTrait.character_id == character_id,
            CharacterTrait.trait.id == trait.id,  # type: ignore [attr-defined]
            fetch_links=True,
        )
        if not character_trait:
            raise NotFoundError(detail="Character trait not found")

    return character_trait


async def provide_inventory_item_by_id(
    inventory_item_id: PydanticObjectId,
) -> CharacterInventory:
    """Provide a inventory item by ID."""
    return await _find_or_404(CharacterInventory, "Inventory item", doc_id=inventory_item_id)


async def provide_note_by_id(note_id: PydanticObjectId) -> Note:
    """Provide a note by ID."""
    return await _find_or_404(Note, "Note", doc_id=note_id)


async def provide_quickroll_by_id(quickroll_id: PydanticObjectId) -> QuickRoll:
    """Provide a quick roll by ID."""
    return await _find_or_404(QuickRoll, "Quick roll", doc_id=quickroll_id)


async def provide_trait_category_by_id(category_id: PydanticObjectId) -> TraitCategory:
    """Provide a trait category by ID."""
    return await _find_or_404(TraitCategory, "Trait category", doc_id=category_id)


async def provide_user_by_id_and_company(user_id: PydanticObjectId, company: Company) -> User:
    """Retrieve a user by ID."""
    return await _find_or_404(User, "User", User.company_id == company.id, doc_id=user_id)


async def provide_user_by_id(user_id: PydanticObjectId) -> User:
    """Provide a user by ID."""
    return await _find_or_404(User, "User", doc_id=user_id)
