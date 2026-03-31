"""Fixtures for the database models."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

import pytest

from vapi.cli.lib.factories import (
    CampaignBookFactory,
    CampaignChapterFactory,
    CampaignFactory,
    CompanyFactory,
    DeveloperFactory,
    UserFactory,
)
from vapi.constants import (
    AUTH_HEADER_KEY,
    AssetParentType,
    AssetType,
    CharacterClass,
    CompanyPermission,
    GameVersion,
    InventoryItemType,
    UserRole,
)
from vapi.db.models import (
    Campaign,
    CampaignBook,
    CampaignChapter,
    Character,
    CharacterConcept,
    CharacterInventory,
    Company,
    Developer,
    DiceRoll,
    DictionaryTerm,
    Note,
    QuickRoll,
    S3Asset,
    Trait,
    TraitCategory,
    User,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)
from vapi.db.models.character import (
    HunterAttributes,
    MageAttributes,
    VampireAttributes,
    WerewolfAttributes,
)
from vapi.db.models.developer import CompanyPermissions

from .factories import (
    CharacterFactory,
    CharacterTraitFactory,
    DiceRollFactory,
    TraitFactory,
)

if TYPE_CHECKING:
    from beanie import PydanticObjectId

    from vapi.db.models import CharacterTrait

pytestmark = pytest.mark.anyio

API_KEY_CACHE: dict[str, str] = {}


def _token_header(developer: Developer) -> dict[str, str]:
    """Build an auth header dict from a developer's cached API key."""
    api_key = API_KEY_CACHE.get(str(developer.id))
    assert api_key is not None, f"Missing cached API key for developer {developer.id}"
    return {AUTH_HEADER_KEY: api_key}


async def _create_character(**kwargs: Any) -> Character:
    """Create a character for testing and save it to the database.

    Args:
        **kwargs: Keyword arguments to pass to the character factory.

    Returns:
        Character: A character object.
    """
    raw_class = kwargs.pop("character_class", None)
    character_class = (
        CharacterClass(raw_class) if raw_class else random.choice(list(CharacterClass))
    )

    vampire_attributes = VampireAttributes()
    werewolf_attributes = WerewolfAttributes()
    mage_attributes = MageAttributes()
    hunter_attributes = HunterAttributes()
    if character_class == CharacterClass.VAMPIRE:
        clan = await VampireClan.find_one(
            VampireClan.is_archived == False, VampireClan.game_versions == GameVersion.V5
        )
        vampire_attributes = VampireAttributes(clan_id=clan.id)
    elif character_class == CharacterClass.WEREWOLF:
        tribe = await WerewolfTribe.find_one(WerewolfTribe.is_archived == False)
        auspice = await WerewolfAuspice.find_one(WerewolfAuspice.is_archived == False)
        werewolf_attributes = WerewolfAttributes(tribe_id=tribe.id, auspice_id=auspice.id)

    character = CharacterFactory().build(
        character_class=character_class,
        vampire_attributes=vampire_attributes,
        werewolf_attributes=werewolf_attributes,
        mage_attributes=mage_attributes,
        hunter_attributes=hunter_attributes,
        **kwargs,
    )

    await character.save()
    return character


@pytest.fixture
async def token_global_admin(base_developer_global_admin: Developer) -> dict[str, str]:
    """Return auth header for the global admin developer."""
    return _token_header(base_developer_global_admin)


@pytest.fixture
async def token_company_owner(base_developer_company_owner: Developer) -> dict[str, str]:
    """Return auth header for the company owner developer."""
    return _token_header(base_developer_company_owner)


@pytest.fixture
async def token_company_admin(base_developer_company_admin: Developer) -> dict[str, str]:
    """Return auth header for the company admin developer."""
    return _token_header(base_developer_company_admin)


@pytest.fixture
async def token_company_user(base_developer_company_user: Developer) -> dict[str, str]:
    """Return auth header for the company user developer."""
    return _token_header(base_developer_company_user)


@pytest.fixture
async def base_company() -> Company:
    """Return the base company for testing, creating it if needed."""
    company = await Company.find_one(Company.is_archived == False, Company.name == "Base Company")
    if not company:
        company = CompanyFactory().build(is_archived=False, name="Base Company")
        await company.save()
    else:
        company.settings = CompanyFactory().build().settings
        await company.save()

    return company


@pytest.fixture
async def base_developer_global_admin() -> Developer:
    """Return a global admin developer, creating it if needed."""
    developer = await Developer.find_one(
        Developer.is_archived == False, Developer.is_global_admin == True
    )
    if not developer:
        developer = DeveloperFactory().build(is_global_admin=True)
        await developer.save()

    api_key = await developer.generate_api_key()
    API_KEY_CACHE[str(developer.id)] = api_key
    return developer


async def _get_or_create_company_developer(
    company: Company, permission: CompanyPermission
) -> Developer:
    """Find or create a developer with the given permission for the company."""
    developer = await Developer.find_one(
        Developer.is_archived == False,
        Developer.is_global_admin == False,
        Developer.companies.company_id == company.id,
        Developer.companies.permission == permission,
    )
    if not developer:
        developer = DeveloperFactory().build(
            is_global_admin=False,
            companies=[
                CompanyPermissions(
                    company_id=company.id,
                    name=company.name,
                    permission=permission,
                )
            ],
        )
        await developer.save()

    api_key = await developer.generate_api_key()
    API_KEY_CACHE[str(developer.id)] = api_key
    return developer


@pytest.fixture
async def base_developer_company_owner(base_company: Company) -> Developer:
    """Return a developer with OWNER permission on the base company."""
    return await _get_or_create_company_developer(base_company, CompanyPermission.OWNER)


@pytest.fixture
async def base_developer_company_admin(base_company: Company) -> Developer:
    """Return a developer with ADMIN permission on the base company."""
    return await _get_or_create_company_developer(base_company, CompanyPermission.ADMIN)


@pytest.fixture
async def base_developer_company_user(base_company: Company) -> Developer:
    """Return a developer with USER permission on the base company."""
    return await _get_or_create_company_developer(base_company, CompanyPermission.USER)


async def _get_or_create_user(company: Company, role: UserRole) -> User:
    """Find or create a user with the given role in the company."""
    user = await User.find_one(
        User.is_archived == False,
        User.company_id == company.id,
        User.role == role,
    )
    if not user:
        user = UserFactory().build(company_id=company.id, is_archived=False, role=role)
        await user.save()

    if user.id not in company.user_ids:
        company.user_ids.append(user.id)
        await company.save()

    return user


@pytest.fixture
async def base_user(base_company: Company) -> User:
    """Return a base player user for testing."""
    return await _get_or_create_user(base_company, UserRole.PLAYER)


@pytest.fixture
async def base_user_storyteller(base_company: Company) -> User:
    """Return a base storyteller user for testing."""
    return await _get_or_create_user(base_company, UserRole.STORYTELLER)


@pytest.fixture
async def base_user_admin(base_company: Company) -> User:
    """Return a base admin user for testing."""
    return await _get_or_create_user(base_company, UserRole.ADMIN)


@pytest.fixture
async def base_campaign(base_company: Company) -> Campaign:
    """Return the base campaign for testing, creating it if needed."""
    campaign = await Campaign.find_one(
        Campaign.company_id == base_company.id,
        Campaign.is_archived == False,
    )
    if not campaign:
        campaign = CampaignFactory().build(company_id=base_company.id, is_archived=False)
        await campaign.save()

    return campaign


@pytest.fixture
async def base_campaign_book(base_campaign: Campaign) -> CampaignBook:
    """Return the base campaign book for testing, creating it if needed."""
    campaign_book = await CampaignBook.find_one(
        CampaignBook.campaign_id == base_campaign.id,
        CampaignBook.is_archived == False,
    )
    if not campaign_book:
        campaign_book = CampaignBookFactory().build(campaign_id=base_campaign.id, is_archived=False)
        await campaign_book.save()

    return campaign_book


@pytest.fixture
async def base_campaign_chapter(base_campaign_book: CampaignBook) -> CampaignChapter:
    """Return the base campaign chapter for testing, creating it if needed."""
    campaign_chapter = await CampaignChapter.find_one(
        CampaignChapter.book_id == base_campaign_book.id,
        CampaignChapter.is_archived == False,
    )
    if not campaign_chapter:
        campaign_chapter = CampaignChapterFactory().build(
            book_id=base_campaign_book.id, is_archived=False
        )
        await campaign_chapter.save()

    return campaign_chapter


@pytest.fixture
async def base_character(
    base_company: Company, base_user: User, base_campaign: Campaign
) -> Character:
    """Return the base character for testing, creating it if needed."""
    character = await Character.find_one(
        Character.company_id == base_company.id,
        Character.user_creator_id == base_user.id,
        Character.user_player_id == base_user.id,
        Character.campaign_id == base_campaign.id,
        Character.is_archived == False,
        Character.name_first == "Base",
        Character.name_last == "Character",
    )
    if not character:
        character = await _create_character(
            company_id=base_company.id,
            user_creator_id=base_user.id,
            user_player_id=base_user.id,
            campaign_id=base_campaign.id,
            is_archived=False,
            name_first="Base",
            name_last="Character",
        )

    return character


@pytest.fixture
async def developer_factory(base_company: Company) -> DeveloperFactory:
    """Return a factory function that creates Developer instances."""

    async def _developer_factory(
        permission: CompanyPermission = CompanyPermission.USER,
        *,
        is_global_admin: bool = False,
        **kwargs: Any,
    ) -> Developer:
        _sentinel = object()
        companies = kwargs.pop("companies", _sentinel)
        if companies is _sentinel:
            companies = [
                CompanyPermissions(
                    company_id=base_company.id,
                    name=base_company.name,
                    permission=permission,
                )
            ]

        developer = DeveloperFactory().build(
            is_global_admin=is_global_admin,
            companies=companies,
            **kwargs,
        )
        await developer.save()
        return developer

    return _developer_factory


@pytest.fixture
async def company_factory() -> CompanyFactory:
    """Return a factory function that creates Company instances."""

    async def _company_factory(
        dev_admin_id: PydanticObjectId | str = None, **kwargs: Any
    ) -> Company:
        company = CompanyFactory().build(**kwargs)
        await company.save()

        if dev_admin_id:
            developer = await Developer.get(dev_admin_id)
            developer.companies.append(
                CompanyPermissions(
                    company_id=company.id, name=company.name, permission=CompanyPermission.ADMIN
                )
            )
            await developer.save()

        return company

    return _company_factory


@pytest.fixture
async def user_factory(base_company) -> UserFactory:
    """Return a factory function that creates User instances."""

    async def _user_factory(
        company_id: PydanticObjectId | str = base_company.id, **kwargs: Any
    ) -> User:
        user = UserFactory().build(**kwargs, company_id=company_id)
        await user.save()

        company = await Company.get(company_id)
        if company:
            company.user_ids.append(user.id)
            await company.save()
        return user

    return _user_factory


@pytest.fixture
async def character_factory(base_company, base_user, base_campaign) -> CharacterFactory:
    """Return a factory function that creates Character instances."""

    async def _character_factory(
        company_id: PydanticObjectId | str = base_company.id,
        user_player_id: PydanticObjectId | str = base_user.id,
        user_creator_id: PydanticObjectId | str = base_user.id,
        campaign_id: PydanticObjectId | str = base_campaign.id,
        **kwargs: Any,
    ) -> Character:
        return await _create_character(
            company_id=company_id,
            user_creator_id=user_creator_id,
            user_player_id=user_player_id,
            campaign_id=campaign_id,
            **kwargs,
        )

    return _character_factory


@pytest.fixture
async def campaign_factory(base_company) -> CampaignFactory:
    """Return a factory function that creates Campaign instances."""

    async def _campaign_factory(
        company_id: PydanticObjectId | str = base_company.id, **kwargs: Any
    ) -> Campaign:
        campaign = CampaignFactory().build(**kwargs, company_id=company_id)
        await campaign.save()
        return campaign

    return _campaign_factory


@pytest.fixture
async def campaign_book_factory(base_campaign: Campaign) -> CampaignBookFactory:
    """Return a factory function that creates CampaignBook instances."""

    async def _campaign_book_factory(**kwargs: Any) -> CampaignBook:
        """Create a campaign book for testing."""
        campaign_id = kwargs.pop("campaign_id", base_campaign.id)
        number = kwargs.pop("number", None)
        if number is None:
            count = await CampaignBook.find(
                CampaignBook.campaign_id == campaign_id,
                CampaignBook.is_archived == False,
            ).count()
            number = count + 1

        campaign_book = CampaignBookFactory().build(
            **kwargs, campaign_id=campaign_id, number=number
        )
        await campaign_book.save()
        return campaign_book

    return _campaign_book_factory


@pytest.fixture
async def campaign_chapter_factory(base_campaign_book: CampaignBook) -> CampaignChapterFactory:
    """Return a factory function that creates CampaignChapter instances."""

    async def _campaign_chapter_factory(**kwargs: Any) -> CampaignChapter:
        """Create a campaign chapter for testing."""
        book_id = kwargs.pop("book_id", base_campaign_book.id)
        number = kwargs.pop("number", None)
        if number is None:
            count = await CampaignChapter.find(
                CampaignChapter.book_id == book_id,
                CampaignChapter.is_archived == False,
            ).count()
            number = count + 1

        campaign_chapter = CampaignChapterFactory().build(**kwargs, book_id=book_id, number=number)
        await campaign_chapter.save()
        return campaign_chapter

    return _campaign_chapter_factory


@pytest.fixture
async def dice_roll_factory(base_company) -> DiceRollFactory:
    """Return a factory function that creates DiceRoll instances."""

    async def _dice_roll_factory(**kwargs: Any) -> DiceRoll:
        """Create a dice roll for testing."""
        if not kwargs.get("company_id"):
            kwargs["company_id"] = base_company.id

        dice_roll = DiceRollFactory().build(**kwargs)
        await dice_roll.save()
        return dice_roll

    return _dice_roll_factory


@pytest.fixture
async def note_factory(base_company) -> Note:
    """Return a factory function that creates Note instances."""

    async def _note_factory(**kwargs: Any) -> Note:
        data = {
            "title": "Test Note",
            "content": "Test content",
            "company_id": base_company.id,
        }

        data |= kwargs

        note = Note(**data)
        await note.save()
        return note

    return _note_factory


@pytest.fixture
async def trait_factory() -> TraitFactory:
    """Return a factory function that creates Trait instances."""

    async def _trait_factory(**kwargs: Any) -> Trait:
        if not kwargs.get("parent_category_id"):
            trait_category = await TraitCategory.find_one(TraitCategory.is_archived == False)
            kwargs["parent_category_id"] = trait_category.id

        if not kwargs.get("is_custom"):
            kwargs["is_custom"] = True

        trait = TraitFactory().build(**kwargs)
        await trait.save()
        return trait

    return _trait_factory


@pytest.fixture
async def character_trait_factory(base_character, trait_factory) -> CharacterTrait:
    """Return a factory function that creates CharacterTrait instances."""

    async def _character_trait_factory(
        character_id: PydanticObjectId = base_character.id,
        trait: Trait | None = None,
        **kwargs: Any,
    ) -> CharacterTrait:
        if not kwargs.get("is_custom"):
            kwargs["is_custom"] = False

        if kwargs["is_custom"] and not trait:
            parent_category = await TraitCategory.find_one(TraitCategory.is_archived == False)
            trait_to_use = TraitFactory().build(
                is_custom=True,
                custom_for_character_id=character_id,
                parent_category_id=parent_category.id,
                sheet_section_id=parent_category.parent_sheet_section_id,
            )
            await trait_to_use.save()
        else:
            trait_to_use = trait or await Trait.find_one(Trait.is_archived == False)

        character_trait = CharacterTraitFactory().build(
            **kwargs, character_id=character_id, trait=trait_to_use
        )
        await character_trait.save()
        return character_trait

    return _character_trait_factory


@pytest.fixture
async def quickroll_factory(base_user) -> QuickRoll:
    """Return a factory function that creates QuickRoll instances."""

    async def _quickroll_factory(**kwargs: Any) -> QuickRoll:
        """Create a quick roll for testing."""
        if "trait_ids" not in kwargs:
            traits = await Trait.find(Trait.is_archived == False).limit(2).to_list()
            kwargs["trait_ids"] = [t.id for t in traits]

        data = {
            "name": "Quick Roll 1",
            "user_id": base_user.id,
            "description": "Quick roll description",
            "is_archived": False,
        }
        data |= kwargs

        quickroll = QuickRoll(**data)
        await quickroll.save()
        return quickroll

    return _quickroll_factory


@pytest.fixture
async def s3asset_factory(base_company, base_user) -> S3Asset:
    """Return a factory function that creates S3Asset instances."""

    async def _s3asset_factory(**kwargs: Any) -> S3Asset:
        data = {
            "asset_type": AssetType.IMAGE,
            "mime_type": "image/jpeg",
            "original_filename": "test.jpg",
            "parent_type": AssetParentType.UNKNOWN,
            "parent_id": None,
            "company_id": base_company.id,
            "uploaded_by": base_user.id,
            "s3_key": "test-key",
            "s3_bucket": "test-bucket",
            "public_url": "https://example.com/test.jpg",
            "is_archived": False,
        }

        data |= kwargs

        s3asset = S3Asset(**data)
        await s3asset.save()
        return s3asset

    return _s3asset_factory


@pytest.fixture
async def inventory_item_factory(base_character) -> CharacterInventory:
    """Return a factory function that creates CharacterInventory instances."""

    async def _inventory_item_factory(**kwargs: Any) -> CharacterInventory:
        data = {
            "character_id": base_character.id,
            "name": "Test Item",
            "description": "Test description",
            "type": InventoryItemType.EQUIPMENT,
            "is_archived": False,
        }

        data |= kwargs

        inventory_item = CharacterInventory(**data)
        await inventory_item.save()
        return inventory_item

    return _inventory_item_factory


@pytest.fixture
async def dictionary_term_factory(base_company) -> DictionaryTerm:
    """Return a factory function that creates DictionaryTerm instances."""

    async def _dictionary_term_factory(**kwargs: Any) -> DictionaryTerm:
        data = {
            "term": "Test Term",
            "definition": "Test definition",
            "link": "https://example.com/test",
            "synonyms": ["Test Synonym", "Test Synonym 2"],
            "company_id": base_company.id,
            "source_type": None,
            "source_id": None,
            "is_archived": False,
        }
        data |= kwargs

        dictionary_term = DictionaryTerm(**data)
        await dictionary_term.save()
        return dictionary_term

    return _dictionary_term_factory


@pytest.fixture
async def character_concept_factory() -> CharacterConcept:
    """Return a factory function that creates CharacterConcept instances."""
    created_concepts = []

    async def _character_concept_factory(**kwargs: Any) -> CharacterConcept:
        data = {
            "name": "Test Concept",
            "description": "Test description",
            "examples": ["Test example", "Test example 2"],
            "company_id": None,
            "is_archived": False,
        }

        data |= kwargs

        character_concept = CharacterConcept(**data)
        await character_concept.save()
        created_concepts.append(character_concept)
        return character_concept

    yield _character_concept_factory
    for concept in created_concepts:
        await concept.delete()
