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

API_KEY_CACHE: dict[str, str] = {}  # cache plaintext API keys by user id for tests


async def _create_character(
    **kwargs: Any,
) -> Character:
    """Create a character for testing and save it to the database.

    Args:
        **kwargs: Keyword arguments to pass to the character factory.

    Returns:
        Character: A character object.
    """
    if kwargs.get("character_class"):
        character_class = CharacterClass(kwargs.get("character_class"))
        del kwargs["character_class"]
    else:
        character_class = random.choice(list(CharacterClass))

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
        tribe = await WerewolfTribe.find_one({"is_archived": False})
        auspice = await WerewolfAuspice.find_one({"is_archived": False})
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
    """Create a token for a global admin.

    Returns:
        str: A token for a global admin.
    """
    api_key = API_KEY_CACHE.get(str(base_developer_global_admin.id))
    assert api_key is not None, "Missing cached API key for base_developer_global_admin"
    return {AUTH_HEADER_KEY: api_key}


@pytest.fixture
async def token_company_owner(base_developer_company_owner) -> dict[str, str]:
    """Create a token for a company owner.

    Returns:
        str: A token for a company owner.
    """
    api_key = API_KEY_CACHE.get(str(base_developer_company_owner.id))
    assert api_key is not None, "Missing cached API key for base_developer_company_owner"
    return {AUTH_HEADER_KEY: api_key}


@pytest.fixture
async def token_company_admin(base_developer_company_admin) -> dict[str, str]:
    """Create a token for a company admin.

    Returns:
        str: A token for a company admin.
    """
    api_key = API_KEY_CACHE.get(str(base_developer_company_admin.id))
    assert api_key is not None, "Missing cached API key for base_developer_company_admin"
    return {AUTH_HEADER_KEY: api_key}


@pytest.fixture
async def token_company_user(base_developer_company_user) -> dict[str, str]:
    """Create a token for a company user.

    Returns:
        str: A token for a company user.
    """
    api_key = API_KEY_CACHE.get(str(base_developer_company_user.id))
    assert api_key is not None, "Missing cached API key for base_developer_company_user"
    return {AUTH_HEADER_KEY: api_key}


@pytest.fixture
async def base_company() -> Company:
    """Create a base company for testing.

    Returns:
        Company: A company object.
    """
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
    """Create a base Developer for testing.

    Returns:
        Developer: A Developer object.
    """
    developer = await Developer.find_one(
        Developer.is_archived == False, Developer.is_global_admin == True
    )
    if not developer:
        developer = DeveloperFactory().build(is_global_admin=True)
        await developer.save()

    api_key = await developer.generate_api_key()
    API_KEY_CACHE[str(developer.id)] = api_key
    return developer


@pytest.fixture
async def base_developer_company_owner(base_company) -> Developer:
    """Create a base Developer for testing.

    Returns:
        Developer: A Developer object.
    """
    developer = await Developer.find_one(
        Developer.is_archived == False,
        Developer.is_global_admin == False,
        Developer.companies.company_id == base_company.id,
        Developer.companies.name == base_company.name,
        Developer.companies.permission == CompanyPermission.OWNER,
    )
    if not developer:
        developer = DeveloperFactory().build(
            is_global_admin=False,
            companies=[
                CompanyPermissions(
                    company_id=base_company.id,
                    name=base_company.name,
                    permission=CompanyPermission.OWNER,
                )
            ],
        )
        await developer.save()

    api_key = await developer.generate_api_key()
    API_KEY_CACHE[str(developer.id)] = api_key

    return developer


@pytest.fixture
async def base_developer_company_admin(base_company) -> Developer:
    """Create a base Developer for testing.

    Returns:
        Developer: A Developer object.
    """
    developer = await Developer.find_one(
        Developer.is_archived == False,
        Developer.is_global_admin == False,
        Developer.companies
        == CompanyPermissions(
            company_id=base_company.id, name=base_company.name, permission=CompanyPermission.ADMIN
        ),
    )
    if not developer:
        developer = DeveloperFactory().build(
            is_global_admin=False,
            companies=[
                CompanyPermissions(
                    company_id=base_company.id,
                    name=base_company.name,
                    permission=CompanyPermission.ADMIN,
                )
            ],
        )
        await developer.save()

    api_key = await developer.generate_api_key()
    API_KEY_CACHE[str(developer.id)] = api_key

    return developer


@pytest.fixture
async def base_developer_company_user(base_company) -> Developer:
    """Create a base Developer for testing.

    Returns:
        Developer: A Developer object.
    """
    developer = await Developer.find_one(
        Developer.is_archived == False,
        Developer.is_global_admin == False,
        Developer.companies
        == CompanyPermissions(
            company_id=base_company.id, name=base_company.name, permission=CompanyPermission.USER
        ),
    )
    if not developer:
        developer = DeveloperFactory().build(
            is_global_admin=False,
            companies=[
                CompanyPermissions(
                    company_id=base_company.id,
                    name=base_company.name,
                    permission=CompanyPermission.USER,
                )
            ],
        )
        await developer.save()

    api_key = await developer.generate_api_key()
    API_KEY_CACHE[str(developer.id)] = api_key

    return developer


@pytest.fixture
async def base_user(base_company) -> User:
    """Create a base user for testing.

    Returns:
        User: A user object.
    """
    user = await User.find_one(
        User.is_archived == False,
        User.company_id == base_company.id,
        User.role == UserRole.PLAYER,
    )
    if not user:
        user = UserFactory().build(
            company_id=base_company.id, is_archived=False, role=UserRole.PLAYER
        )
        await user.save()

    if user.id not in base_company.user_ids:
        base_company.user_ids.append(user.id)
        await base_company.save()

    return user


@pytest.fixture
async def base_user_storyteller(base_company) -> User:
    """Create a base storyteller user for testing.

    Returns:
        User: A user object.
    """
    user = await User.find_one(
        User.is_archived == False,
        User.company_id == base_company.id,
        User.role == UserRole.STORYTELLER,
    )
    if not user:
        user = UserFactory().build(
            company_id=base_company.id, is_archived=False, role=UserRole.STORYTELLER
        )
        await user.save()

    if user.id not in base_company.user_ids:
        base_company.user_ids.append(user.id)
        await base_company.save()

    return user


@pytest.fixture
async def base_user_admin(base_company) -> User:
    """Create a base admin user for testing.

    Returns:
        User: A user object.
    """
    user = await User.find_one(
        User.is_archived == False,
        User.company_id == base_company.id,
        User.role == UserRole.ADMIN,
    )
    if not user:
        user = UserFactory().build(
            company_id=base_company.id, is_archived=False, role=UserRole.ADMIN
        )
        await user.save()

    if user.id not in base_company.user_ids:
        base_company.user_ids.append(user.id)
        await base_company.save()

    return user


@pytest.fixture
async def base_user_player(base_company) -> User:
    """Create a base user for testing.

    Returns:
        User: A user object.
    """
    user = await User.find_one(
        User.is_archived == False,
        User.company_id == base_company.id,
        User.role == UserRole.PLAYER,
    )
    if not user:
        user = UserFactory().build(
            company_id=base_company.id, is_archived=False, role=UserRole.PLAYER
        )
        await user.save()

    if user.id not in base_company.user_ids:
        base_company.user_ids.append(user.id)
        await base_company.save()

    return user


@pytest.fixture
async def base_campaign(base_company) -> Campaign:
    """Create a base campaign for testing.

    Returns:
        Campaign: A campaign object.
    """
    campaign = await Campaign.find_one(
        Campaign.company_id == base_company.id,
        Campaign.is_archived == False,
    )
    if not campaign:
        campaign = CampaignFactory().build(company_id=base_company.id, is_archived=False)
        await campaign.save()

    return campaign


@pytest.fixture
async def base_campaign_book(base_campaign) -> CampaignBook:
    """Create a base campaign book for testing.

    Returns:
        CampaignBook: A campaign book object.
    """
    campaign_book = await CampaignBook.find_one(
        CampaignBook.campaign_id == base_campaign.id,
        CampaignBook.is_archived == False,
    )
    if not campaign_book:
        campaign_book = CampaignBookFactory().build(campaign_id=base_campaign.id, is_archived=False)
        await campaign_book.save()

    return campaign_book


@pytest.fixture
async def base_campaign_chapter(base_campaign_book) -> CampaignChapter:
    """Create a base campaign chapter for testing.

    Returns:
        CampaignChapter: A campaign chapter object.
    """
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
async def base_character(base_company, base_user, base_campaign) -> Character:
    """Create a base character for testing.

    Returns:
        Character: A character object.
    """
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


#########################################################################
@pytest.fixture
async def developer_factory(base_company: Company) -> DeveloperFactory:
    """Create a developer factory for testing.

    Returns:
        DeveloperFactory: A developer factory object.
    """
    created_developers = []  # Track all created developers

    async def _developer_factory(
        permission: CompanyPermission = CompanyPermission.USER,
        *,
        is_global_admin: bool = False,
        **kwargs: Any,
    ) -> Developer:
        if "companies" in kwargs:
            companies = kwargs["companies"]
            del kwargs["companies"]
        else:
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
        created_developers.append(developer)
        return developer

    yield _developer_factory

    # Cleanup: delete all developers created during the test
    for developer in created_developers:
        await developer.delete()


@pytest.fixture
async def company_factory() -> CompanyFactory:
    """Create a company factory for testing.

    Returns:
        CompanyFactory: A company factory object.
    """
    created_companies = []  # Track all created companies

    async def _company_factory(
        dev_admin_id: PydanticObjectId | str = None, **kwargs: Any
    ) -> Company:
        company = CompanyFactory().build(**kwargs)
        await company.save()
        created_companies.append(company)

        if dev_admin_id:
            developer = await Developer.get(dev_admin_id)
            developer.companies.append(
                CompanyPermissions(
                    company_id=company.id, name=company.name, permission=CompanyPermission.ADMIN
                )
            )
            await developer.save()

        return company

    yield _company_factory

    # Cleanup: delete all companies created during the test
    for company in created_companies:
        await company.delete()


@pytest.fixture
async def user_factory(base_company, debug) -> UserFactory:
    """Create a user factory for testing.

    Returns:
        UserFactory: A user factory object.
    """
    created_users = []  # Track all created users

    async def _user_factory(
        company_id: PydanticObjectId | str = base_company.id, **kwargs: Any
    ) -> User:
        user = UserFactory().build(**kwargs, company_id=company_id)
        await user.save()

        company = await Company.get(company_id)
        if company:
            company.user_ids.append(user.id)
            await company.save()
        created_users.append(user)
        return user

    yield _user_factory

    # Cleanup: delete all users created during the test
    for user in created_users:
        await user.delete()


@pytest.fixture
async def character_factory(base_company, base_user, base_campaign) -> CharacterFactory:
    """Create a character factory for testing.

    Returns:
        CharacterFactory: A character factory object.
    """
    created_characters = []  # Track all created characters

    async def _character_factory(
        company_id: PydanticObjectId | str = base_company.id,
        user_player_id: PydanticObjectId | str = base_user.id,
        user_creator_id: PydanticObjectId | str = base_user.id,
        campaign_id: PydanticObjectId | str = base_campaign.id,
        **kwargs: Any,
    ) -> Character:
        character = await _create_character(
            company_id=company_id,
            user_creator_id=user_creator_id,
            user_player_id=user_player_id,
            campaign_id=campaign_id,
            **kwargs,
        )
        created_characters.append(character)
        return character

    yield _character_factory

    # Cleanup: delete all characters created during the test
    for character in created_characters:
        await character.delete()


@pytest.fixture
async def campaign_factory(base_company) -> CampaignFactory:
    """Create a campaign factory for testing.

    Returns:
        CampaignFactory: A campaign factory object.
    """
    created_campaigns = []  # Track all created campaigns

    async def _campaign_factory(
        company_id: PydanticObjectId | str = base_company.id, **kwargs: Any
    ) -> Campaign:
        campaign = CampaignFactory().build(**kwargs, company_id=company_id)
        await campaign.save()
        created_campaigns.append(campaign)
        return campaign

    yield _campaign_factory

    # Cleanup: delete all campaigns created during the test
    for campaign in created_campaigns:
        await campaign.delete()


@pytest.fixture
async def campaign_book_factory(base_campaign: Campaign) -> CampaignBookFactory:
    """Create a campaign book factory for testing.

    Returns:
        CampaignBookFactory: A campaign book factory object.
    """
    created_campaign_books = []  # Track all created campaign books

    async def _campaign_book_factory(**kwargs: Any) -> CampaignBook:
        """Create a campaign book for testing.

        Args:
            **kwargs: Keyword arguments to pass to the campaign book factory.

        Returns:
            CampaignBook: A campaign book object.
        """
        if kwargs.get("campaign_id"):
            campaign_id = kwargs.get("campaign_id")
            kwargs.pop("campaign_id")
        else:
            campaign_id = base_campaign.id

        if kwargs.get("number"):
            number = kwargs.get("number")
            kwargs.pop("number")
        else:
            count = await CampaignBook.find(
                CampaignBook.campaign_id == campaign_id,
                CampaignBook.is_archived == False,
            ).count()
            number = count + 1

        campaign_book = CampaignBookFactory().build(
            **kwargs, campaign_id=campaign_id, number=number
        )
        await campaign_book.save()
        created_campaign_books.append(campaign_book)
        return campaign_book

    yield _campaign_book_factory

    # Cleanup: delete all campaign books created during the test
    for campaign_book in created_campaign_books:
        await campaign_book.delete()


@pytest.fixture
async def campaign_chapter_factory(base_campaign_book: CampaignBook) -> CampaignChapterFactory:
    """Create a campaign book factory for testing.

    Returns:
        CampaignChapterFactory: A campaign chapter factory object.
    """
    created_campaign_chapters = []  # Track all created campaign chapters

    async def _campaign_chapter_factory(**kwargs: Any) -> CampaignChapter:
        """Create a campaign book for testing.

        Args:
            **kwargs: Keyword arguments to pass to the campaign chapter factory.

        Returns:
            CampaignChapter: A campaign chapter object.
        """
        if kwargs.get("book_id"):
            book_id = kwargs.get("book_id")
            kwargs.pop("book_id")
        else:
            book_id = base_campaign_book.id

        if kwargs.get("number"):
            number = kwargs.get("number")
            kwargs.pop("number")
        else:
            count = await CampaignChapter.find(
                CampaignChapter.book_id == book_id,
                CampaignChapter.is_archived == False,
            ).count()
            number = count + 1

        campaign_chapter = CampaignChapterFactory().build(**kwargs, book_id=book_id, number=number)
        await campaign_chapter.save()
        created_campaign_chapters.append(campaign_chapter)
        return campaign_chapter

    yield _campaign_chapter_factory

    # Cleanup: delete all campaign chapters created during the test
    for campaign_chapter in created_campaign_chapters:
        await campaign_chapter.delete()


@pytest.fixture
async def dice_roll_factory(base_company) -> DiceRollFactory:
    """Create a dice roll factory for testing.

    Returns:
        DiceRollFactory: A dice roll factory object.
    """
    created_dice_rolls = []  # Track all created dice rolls

    async def _dice_roll_factory(**kwargs: Any) -> DiceRollFactory:
        """Create a dice roll for testing."""
        if not kwargs.get("company_id"):
            kwargs["company_id"] = base_company.id

        dice_roll = DiceRollFactory().build(**kwargs)
        await dice_roll.save()
        created_dice_rolls.append(dice_roll)
        return dice_roll

    yield _dice_roll_factory

    # Cleanup: delete all dice rolls created during the test
    for dice_roll in created_dice_rolls:
        await dice_roll.delete()


@pytest.fixture
async def note_factory(base_company) -> Note:
    """Create a note factory for testing.

    Returns:
        NoteFactory: A note factory object.
    """
    created_notes = []  # Track all created notes

    async def _note_factory(**kwargs: Any) -> Note:
        data = {
            "title": "Test Note",
            "content": "Test content",
            "company_id": base_company.id,
        }

        for key, value in kwargs.items():
            data[key] = value  # noqa: PERF403

        note = Note(**data)
        await note.save()
        created_notes.append(note)  # Track the created note
        return note

    yield _note_factory

    # Cleanup: delete all notes created during the test
    for note in created_notes:
        await note.delete()


@pytest.fixture
async def trait_factory() -> TraitFactory:
    """Create a trait factory for testing.

    Returns:
        TraitFactory: A trait factory object.
    """
    created_traits = []  # Track all created traits

    async def _trait_factory(**kwargs: Any) -> Trait:
        if not kwargs.get("parent_category_id"):
            trait_category = await TraitCategory.find_one(TraitCategory.is_archived == False)
            kwargs["parent_category_id"] = trait_category.id

        if not kwargs.get("is_custom"):
            kwargs["is_custom"] = True

        trait = TraitFactory().build(**kwargs)
        await trait.save()
        created_traits.append(trait)
        return trait

    yield _trait_factory

    # Cleanup: delete all traits created during the test
    for trait in created_traits:
        await trait.delete()


@pytest.fixture
async def character_trait_factory(base_character, trait_factory) -> CharacterTrait:
    """Create a character trait factory for testing.

    Returns:
        CharacterTraitFactory: A character trait factory object.
    """
    created_traits: list[CharacterTrait] = []

    async def _character_trait_factory(
        character_id: PydanticObjectId = base_character.id,
        trait: Trait | None = None,
        **kwargs: Any,
    ) -> CharacterTrait:
        """Create a character trait for testing.

        Args:
            character_id: The ID of the character to create the trait for.
            trait: The trait to create the trait for.
            **kwargs: Keyword arguments to pass to the character trait factory.

        Returns:
            CharacterTrait: A character trait object.
        """
        if not kwargs.get("is_custom"):
            kwargs["is_custom"] = False

        if kwargs["is_custom"] and not trait:
            parent_category = await TraitCategory.find_one(TraitCategory.is_archived == False)
            trait_to_use = TraitFactory().build(
                is_custom=True,
                custom_for_character_id=character_id,
                parent_category_id=parent_category.id,
            )
            await trait_to_use.save()
        else:
            trait_to_use = trait or await Trait.find_one(Trait.is_archived == False)

        character_trait = CharacterTraitFactory().build(
            **kwargs, character_id=character_id, trait=trait_to_use
        )
        await character_trait.save()
        return character_trait

    yield _character_trait_factory

    # Cleanup all created traits after test completes
    for character_trait in created_traits:
        await character_trait.delete()


@pytest.fixture
async def quickroll_factory(base_user) -> QuickRoll:
    """Create a quick roll factory for testing.

    Returns:
        QuickRoll: A quick roll object.
    """
    created_quickrolls = []  # Track all created quickrolls

    async def _quickroll_factory(**kwargs: Any) -> QuickRoll:
        """Create a quick roll for testing."""
        if not kwargs.get("trait_ids"):
            trait_ids = await Trait.find(Trait.is_archived == False).limit(2).to_list()
            kwargs["trait_ids"] = [trait.id for trait in trait_ids]

        quickroll = QuickRoll(
            name=kwargs.get("name") or "Quick Roll 1",
            user_id=kwargs.get("user_id") or base_user.id,
            trait_ids=kwargs.get("trait_ids") or [],
            description=kwargs.get("description") or "Quick roll description",
            is_archived=kwargs.get("is_archived", False),
        )
        await quickroll.save()
        created_quickrolls.append(quickroll)
        return quickroll

    yield _quickroll_factory

    # Cleanup: delete all quickrolls created during the test
    for quickroll in created_quickrolls:
        await quickroll.delete()


@pytest.fixture
async def s3asset_factory(base_company, base_user) -> S3Asset:
    """Create a note factory for testing.

    Returns:
        NoteFactory: A note factory object.
    """
    created_assets = []  # Track all created assets

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

        for key, value in kwargs.items():
            data[key] = value  # noqa: PERF403

        s3asset = S3Asset(**data)
        await s3asset.save()
        created_assets.append(s3asset)
        return s3asset

    yield _s3asset_factory

    # Cleanup: delete all assets created during the test
    for s3asset in created_assets:
        await s3asset.delete()


@pytest.fixture
async def inventory_item_factory(base_character) -> CharacterInventory:
    """Create a inventory item factory for testing.

    Returns:
        InventoryItemFactory: A inventory item factory object.
    """
    created_items = []  # Track all created items

    async def _inventory_item_factory(**kwargs: Any) -> CharacterInventory:
        data = {
            "character_id": base_character.id,
            "name": "Test Item",
            "description": "Test description",
            "type": InventoryItemType.EQUIPMENT,
            "is_archived": False,
        }

        for key, value in kwargs.items():
            data[key] = value  # noqa: PERF403

        inventory_item = CharacterInventory(**data)
        await inventory_item.save()
        created_items.append(inventory_item)
        return inventory_item

    yield _inventory_item_factory

    # Cleanup: delete all assets created during the test
    for inventory_item in created_items:
        await inventory_item.delete()


@pytest.fixture
async def dictionary_term_factory(base_company) -> DictionaryTerm:
    """Create a dictionary term factory for testing.

    Returns:
        DictionaryTermFactory: A dictionary term factory object.
    """
    created_terms = []  # Track all created terms

    async def _dictionary_term_factory(**kwargs: Any) -> DictionaryTerm:
        data = {
            "term": "Test Term",
            "definition": "Test definition",
            "link": "https://example.com/test",
            "synonyms": ["Test Synonym", "Test Synonym 2"],
            "company_id": base_company.id,
            "is_archived": False,
            "is_global": True,
        }

        for key, value in kwargs.items():
            data[key] = value  # noqa: PERF403

        dictionary_term = DictionaryTerm(**data)
        await dictionary_term.save()
        created_terms.append(dictionary_term)
        return dictionary_term

    yield _dictionary_term_factory

    # Cleanup: delete all terms created during the test
    for dictionary_term in created_terms:
        await dictionary_term.delete()


@pytest.fixture
async def character_concept_factory() -> CharacterConcept:
    """Create a character concept factory for testing.

    Returns:
        CharacterConceptFactory: A character concept factory object.
    """
    created_concepts = []  # Track all created concepts

    async def _character_concept_factory(**kwargs: Any) -> CharacterConcept:
        data = {
            "name": "Test Concept",
            "description": "Test description",
            "examples": ["Test example", "Test example 2"],
            "company_id": None,
            "is_archived": False,
        }

        for key, value in kwargs.items():
            data[key] = value  # noqa: PERF403

        character_concept = CharacterConcept(**data)
        await character_concept.save()
        created_concepts.append(character_concept)
        return character_concept

    yield _character_concept_factory

    # Cleanup: delete all concepts created during the test
    for character_concept in created_concepts:
        await character_concept.delete()
