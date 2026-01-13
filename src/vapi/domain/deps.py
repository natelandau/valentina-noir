"""Domain dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from beanie import PydanticObjectId  # noqa: TC002
from beanie.operators import Or
from litestar.params import Parameter

from vapi.db.models import (
    Campaign,
    CampaignBook,
    CampaignChapter,
    Character,
    CharacterConcept,
    CharacterInventory,
    CharacterTrait,
    CharSheetSection,
    Company,
    Developer,
    DictionaryTerm,
    HunterEdge,
    HunterEdgePerk,
    Note,
    QuickRoll,
    S3Asset,
    Trait,
    TraitCategory,
    User,
    VampireClan,
    WerewolfAuspice,
    WerewolfGift,
    WerewolfRite,
    WerewolfTribe,
)
from vapi.lib.exceptions import NotFoundError

if TYPE_CHECKING:
    from litestar import Request


async def provide_s3_asset_by_id(asset_id: PydanticObjectId) -> S3Asset:
    """Provide an S3 asset by ID."""
    s3_asset = await S3Asset.find_one(
        S3Asset.id == asset_id,
        S3Asset.is_archived == False,
    )
    if not s3_asset:
        raise NotFoundError(detail="S3 asset not found")
    return s3_asset


async def provide_developer_from_request(request: Request) -> Developer:
    """Provide a Developer object from the request."""
    developer = await Developer.find_one(
        Developer.id == request.user.id,
        Developer.is_archived == False,
    )

    if not developer:
        raise NotFoundError(detail="User not found")

    return developer


async def provide_developer_by_id(
    developer_id: Annotated[
        PydanticObjectId, Parameter(title="Developer ID", description="The user to act on.")
    ],
) -> Developer:
    """Provide a Developer by ID."""
    developer = await Developer.find_one(
        Developer.id == developer_id,
        Developer.is_archived == False,
    )
    if not developer:
        raise NotFoundError(detail="User not found")
    return developer


async def provide_campaign_by_id(campaign_id: PydanticObjectId, company: Company) -> Campaign:
    """Provide a campaign by ID."""
    campaign = await Campaign.find_one(
        Campaign.id == campaign_id,
        Campaign.is_archived == False,
        Campaign.company_id == company.id,
    )
    if not campaign:
        raise NotFoundError(detail="Campaign not found")
    return campaign


async def provide_campaign_book_by_id(
    book_id: PydanticObjectId, campaign: Campaign
) -> CampaignBook:
    """Provide a campaign book by ID."""
    campaign_book = await CampaignBook.find_one(
        CampaignBook.id == book_id,
        CampaignBook.is_archived == False,
        CampaignBook.campaign_id == campaign.id,
    )
    if not campaign_book:
        raise NotFoundError(detail="Campaign book not found")
    return campaign_book


async def provide_campaign_chapter_by_id(
    chapter_id: PydanticObjectId, book: CampaignBook
) -> CampaignChapter:
    """Provide a campaign chapter by ID."""
    campaign_chapter = await CampaignChapter.find_one(
        CampaignChapter.id == chapter_id,
        CampaignChapter.is_archived == False,
        CampaignChapter.book_id == book.id,
    )
    if not campaign_chapter:
        raise NotFoundError(detail="Campaign chapter not found")
    return campaign_chapter


async def provide_company_by_id(
    company_id: Annotated[
        PydanticObjectId, Parameter(title="Company ID", description="The company to act on.")
    ],
) -> Company:
    """Provide a company by ID."""
    company = await Company.find_one(
        Company.id == company_id,
        Company.is_archived == False,
    )
    if not company:
        raise NotFoundError(detail="Company 'not found")
    return company


async def provide_character_by_id_and_company(
    character_id: PydanticObjectId, company: Company
) -> Character:
    """Provide a character by ID."""
    character = await Character.find_one(
        Character.id == character_id,
        Character.is_archived == False,
        Character.company_id == company.id,
    )
    if not character:
        raise NotFoundError(detail="Character not found")
    return character


async def provide_character_blueprint_section_by_id(
    section_id: PydanticObjectId,
) -> CharSheetSection:
    """Provide a character sheet section by ID."""
    section = await CharSheetSection.find_one(
        CharSheetSection.id == section_id,
        CharSheetSection.is_archived == False,
    )
    if not section:
        raise NotFoundError(detail="Character sheet section not found")
    return section


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


async def provide_character_concept_by_id(
    company: Company, concept_id: PydanticObjectId
) -> CharacterConcept:
    """Provide a character concept by ID."""
    concept = await CharacterConcept.find_one(
        CharacterConcept.id == concept_id,
        CharacterConcept.is_archived == False,
        Or(CharacterConcept.company_id == company.id, CharacterConcept.company_id == None),
    )
    if not concept:
        raise NotFoundError(detail="Character concept not found")
    return concept


async def provide_vampire_clan_by_id(vampire_clan_id: PydanticObjectId) -> VampireClan:
    """Provide a vampire clan by ID."""
    vampire_clan = await VampireClan.find_one(
        VampireClan.id == vampire_clan_id,
        VampireClan.is_archived == False,
    )
    if not vampire_clan:
        raise NotFoundError(detail="Vampire clan not found")
    return vampire_clan


async def provide_werewolf_tribe_by_id(werewolf_tribe_id: PydanticObjectId) -> WerewolfTribe:
    """Provide a werewolf tribe by ID."""
    werewolf_tribe = await WerewolfTribe.find_one(
        WerewolfTribe.id == werewolf_tribe_id,
        WerewolfTribe.is_archived == False,
    )
    if not werewolf_tribe:
        raise NotFoundError(detail="Werewolf tribe not found")
    return werewolf_tribe


async def provide_werewolf_auspice_by_id(werewolf_auspice_id: PydanticObjectId) -> WerewolfAuspice:
    """Provide a werewolf auspice by ID."""
    werewolf_auspice = await WerewolfAuspice.find_one(
        WerewolfAuspice.id == werewolf_auspice_id,
        WerewolfAuspice.is_archived == False,
    )
    if not werewolf_auspice:
        raise NotFoundError(detail="Werewolf auspice not found")
    return werewolf_auspice


async def provide_werewolf_gift_by_id(werewolf_gift_id: PydanticObjectId) -> WerewolfGift:
    """Provide a werewolf gift by ID."""
    werewolf_gift = await WerewolfGift.find_one(
        WerewolfGift.id == werewolf_gift_id,
        WerewolfGift.is_archived == False,
    )
    if not werewolf_gift:
        raise NotFoundError(detail="Werewolf gift not found")
    return werewolf_gift


async def provide_werewolf_rite_by_id(werewolf_rite_id: PydanticObjectId) -> WerewolfRite:
    """Provide a werewolf rite by ID."""
    werewolf_rite = await WerewolfRite.find_one(
        WerewolfRite.id == werewolf_rite_id,
        WerewolfRite.is_archived == False,
    )
    if not werewolf_rite:
        raise NotFoundError(detail="Werewolf rite not found")
    return werewolf_rite


async def provide_hunter_edge_by_id(hunter_edge_id: PydanticObjectId) -> HunterEdge:
    """Provide a hunter edge by ID."""
    hunter_edge = await HunterEdge.find_one(
        HunterEdge.id == hunter_edge_id,
        HunterEdge.is_archived == False,
    )
    if not hunter_edge:
        raise NotFoundError(detail="Hunter edge not found")
    return hunter_edge


async def provide_hunter_edge_perk_by_id(hunter_edge_perk_id: PydanticObjectId) -> HunterEdgePerk:
    """Provide a hunter edge perk by ID."""
    hunter_edge_perk = await HunterEdgePerk.find_one(
        HunterEdgePerk.id == hunter_edge_perk_id,
        HunterEdgePerk.is_archived == False,
    )
    if not hunter_edge_perk:
        raise NotFoundError(detail="Hunter edge perk not found")
    return hunter_edge_perk


async def provide_dictionary_term_by_id(
    company: Company, dictionary_term_id: PydanticObjectId
) -> DictionaryTerm:
    """Provide a dictionary term by ID."""
    dictionary_term = await DictionaryTerm.find_one(
        DictionaryTerm.id == dictionary_term_id,
        DictionaryTerm.is_archived == False,
        Or(DictionaryTerm.company_id == company.id, DictionaryTerm.is_global == True),
    )
    if not dictionary_term:
        raise NotFoundError(detail="Dictionary term not found")
    return dictionary_term


async def provide_inventory_item_by_id(inventory_item_id: PydanticObjectId) -> CharacterInventory:
    """Provide a inventory item by ID."""
    inventory_item = await CharacterInventory.find_one(
        CharacterInventory.id == inventory_item_id,
        CharacterInventory.is_archived == False,
    )
    if not inventory_item:
        raise NotFoundError(detail="Inventory item not found")
    return inventory_item


async def provide_note_by_id(note_id: PydanticObjectId) -> Note:
    """Provide a note by ID."""
    note = await Note.find_one(
        Note.id == note_id,
        Note.is_archived == False,
    )
    if not note:
        raise NotFoundError(detail="Note not found")
    return note


async def provide_quickroll_by_id(quickroll_id: PydanticObjectId) -> QuickRoll:
    """Provide a quick roll by ID."""
    quickroll = await QuickRoll.find_one(
        QuickRoll.id == quickroll_id,
        QuickRoll.is_archived == False,
    )
    if not quickroll:
        raise NotFoundError(detail="Quick roll not found")
    return quickroll


async def provide_trait_by_id(trait_id: PydanticObjectId) -> Trait:
    """Provide a trait by ID."""
    trait = await Trait.find_one(
        Trait.id == trait_id,
        Trait.is_archived == False,
    )
    if not trait:
        raise NotFoundError(detail="Trait not found")
    return trait


async def provide_trait_category_by_id(category_id: PydanticObjectId) -> TraitCategory:
    """Provide a trait category by ID."""
    category = await TraitCategory.find_one(
        TraitCategory.id == category_id,
        TraitCategory.is_archived == False,
    )
    if not category:
        raise NotFoundError(detail="Trait category not found")
    return category


async def provide_user_by_id_and_company(user_id: PydanticObjectId, company: Company) -> User:
    """Retrieve a user by ID."""
    user = await User.find_one(
        User.id == user_id,
        User.is_archived == False,
        User.company_id == company.id,
    )
    if not user:
        raise NotFoundError(detail="User not found")

    return user


async def provide_user_by_id(user_id: PydanticObjectId) -> User:
    """Provide a user by ID."""
    user = await User.find_one(
        User.id == user_id,
        User.is_archived == False,
    )
    if not user:
        raise NotFoundError(detail="User not found")
    return user
