"""Unit tests for domain dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from beanie import PydanticObjectId

from vapi.constants import InventoryItemType
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
from vapi.domain import deps, pg_deps
from vapi.lib.exceptions import NotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.sql_models.notes import Note as PgNote
    from vapi.db.sql_models.quickroll import QuickRoll as PgQuickRoll

pytestmark = pytest.mark.anyio


class TestProvideS3AssetById:
    """Test provide_s3_asset_by_id dependency."""

    async def test_returns_s3_asset_when_found(
        self, s3asset_factory: Callable[..., S3Asset]
    ) -> None:
        """Verify returning an S3 asset when found by ID."""
        # Given an S3 asset exists in the database
        s3_asset = await s3asset_factory()
        result = await deps.provide_s3_asset_by_id(s3_asset.id)
        assert result.id == s3_asset.id

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when S3 asset does not exist."""
        # Given a non-existent S3 asset ID
        non_existent_id = PydanticObjectId()
        with pytest.raises(NotFoundError, match="S3 asset not found"):
            await deps.provide_s3_asset_by_id(non_existent_id)

    async def test_raises_not_found_when_archived(
        self, s3asset_factory: Callable[..., S3Asset]
    ) -> None:
        """Verify raising NotFoundError when S3 asset is archived."""
        # Given an archived S3 asset exists in the database
        s3_asset = await s3asset_factory(is_archived=True)
        with pytest.raises(NotFoundError, match="S3 asset not found"):
            await deps.provide_s3_asset_by_id(s3_asset.id)


class TestProvideDeveloperFromRequest:
    """Test provide_developer_from_request dependency."""

    async def test_returns_developer_when_found(
        self,
        developer_factory: Callable[..., Developer],
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify returning a developer when found from request user ID."""
        # Given a developer exists in the database
        developer = await developer_factory()

        # Given a request with the developer's ID as the user
        mock_request = mocker.MagicMock()
        mock_request.user.id = developer.id

        # When we provide the developer from the request
        result = await deps.provide_developer_from_request(mock_request)

        # Then the developer is returned
        assert result.id == developer.id

    async def test_raises_not_found_when_missing(
        self,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify raising NotFoundError when developer does not exist."""
        # Given a request with a non-existent user ID
        mock_request = mocker.MagicMock()
        mock_request.user.id = PydanticObjectId()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="User not found"):
            await deps.provide_developer_from_request(mock_request)

    async def test_raises_not_found_when_archived(
        self,
        developer_factory: Callable[..., Developer],
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify raising NotFoundError when developer is archived."""
        # Given an archived developer exists in the database
        developer = await developer_factory(is_archived=True)

        # Given a request with the archived developer's ID
        mock_request = mocker.MagicMock()
        mock_request.user.id = developer.id

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="User not found"):
            await deps.provide_developer_from_request(mock_request)


class TestProvideDeveloperById:
    """Test provide_developer_by_id dependency."""

    async def test_returns_developer_when_found(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify returning a developer when found by ID."""
        # Given a developer exists in the database
        developer = await developer_factory()

        # When we provide the developer by ID
        result = await deps.provide_developer_by_id(developer.id)

        # Then the developer is returned
        assert result.id == developer.id

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when developer does not exist."""
        # Given a non-existent developer ID
        non_existent_id = PydanticObjectId()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="User not found"):
            await deps.provide_developer_by_id(non_existent_id)

    async def test_raises_not_found_when_archived(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify raising NotFoundError when developer is archived."""
        # Given an archived developer exists in the database
        developer = await developer_factory(is_archived=True)

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="User not found"):
            await deps.provide_developer_by_id(developer.id)


class TestProvideCompanyById:
    """Test provide_company_by_id dependency."""

    async def test_returns_company_when_found(self, base_company: Company) -> None:
        """Verify returning a company when found by ID."""
        # Given a company exists (from fixture)
        # When we provide the company by ID
        result = await deps.provide_company_by_id(base_company.id)

        # Then the company is returned
        assert result.id == base_company.id

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when company does not exist."""
        # Given a non-existent company ID
        non_existent_id = PydanticObjectId()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Company"):
            await deps.provide_company_by_id(non_existent_id)

    async def test_raises_not_found_when_archived(
        self, company_factory: Callable[..., Company]
    ) -> None:
        """Verify raising NotFoundError when company is archived."""
        # Given an archived company exists in the database
        company = await company_factory(is_archived=True)

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Company"):
            await deps.provide_company_by_id(company.id)


class TestProvideCampaignById:
    """Test provide_campaign_by_id dependency."""

    async def test_returns_campaign_when_found(
        self, base_company: Company, base_campaign: Campaign
    ) -> None:
        """Verify returning a campaign when found by ID and company."""
        # Given a campaign exists (from fixture)
        # When we provide the campaign by ID
        result = await deps.provide_campaign_by_id(base_campaign.id, base_company)

        # Then the campaign is returned
        assert result.id == base_campaign.id

    async def test_raises_not_found_when_missing(self, base_company: Company) -> None:
        """Verify raising NotFoundError when campaign does not exist."""
        # Given a non-existent campaign ID
        non_existent_id = PydanticObjectId()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Campaign not found"):
            await deps.provide_campaign_by_id(non_existent_id, base_company)

    async def test_raises_not_found_when_wrong_company(
        self, base_campaign: Campaign, company_factory: Callable[..., Company]
    ) -> None:
        """Verify raising NotFoundError when campaign belongs to different company."""
        # Given a campaign belongs to a different company
        other_company = await company_factory()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Campaign not found"):
            await deps.provide_campaign_by_id(base_campaign.id, other_company)


class TestProvideCampaignBookById:
    """Test provide_campaign_book_by_id dependency."""

    async def test_returns_campaign_book_when_found(
        self, base_campaign: Campaign, base_campaign_book: CampaignBook
    ) -> None:
        """Verify returning a campaign book when found by ID and campaign."""
        # Given a campaign book exists (from fixture)
        # When we provide the campaign book by ID
        result = await deps.provide_campaign_book_by_id(base_campaign_book.id, base_campaign)

        # Then the campaign book is returned
        assert result.id == base_campaign_book.id

    async def test_raises_not_found_when_missing(self, base_campaign: Campaign) -> None:
        """Verify raising NotFoundError when campaign book does not exist."""
        # Given a non-existent campaign book ID
        non_existent_id = PydanticObjectId()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Campaign book not found"):
            await deps.provide_campaign_book_by_id(non_existent_id, base_campaign)

    async def test_raises_not_found_when_wrong_campaign(
        self, base_campaign_book: CampaignBook, campaign_factory: Callable[..., Campaign]
    ) -> None:
        """Verify raising NotFoundError when book belongs to different campaign."""
        # Given a campaign book belongs to a different campaign
        other_campaign = await campaign_factory()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Campaign book not found"):
            await deps.provide_campaign_book_by_id(base_campaign_book.id, other_campaign)


class TestProvideCampaignChapterById:
    """Test provide_campaign_chapter_by_id dependency."""

    async def test_returns_campaign_chapter_when_found(
        self, base_campaign_book: CampaignBook, base_campaign_chapter: CampaignChapter
    ) -> None:
        """Verify returning a campaign chapter when found by ID and book."""
        # Given a campaign chapter exists (from fixture)
        # When we provide the campaign chapter by ID
        result = await deps.provide_campaign_chapter_by_id(
            base_campaign_chapter.id, base_campaign_book
        )

        # Then the campaign chapter is returned
        assert result.id == base_campaign_chapter.id

    async def test_raises_not_found_when_missing(self, base_campaign_book: CampaignBook) -> None:
        """Verify raising NotFoundError when campaign chapter does not exist."""
        # Given a non-existent campaign chapter ID
        non_existent_id = PydanticObjectId()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Campaign chapter not found"):
            await deps.provide_campaign_chapter_by_id(non_existent_id, base_campaign_book)

    async def test_raises_not_found_when_wrong_book(
        self,
        base_campaign_chapter: CampaignChapter,
        campaign_book_factory: Callable[..., CampaignBook],
    ) -> None:
        """Verify raising NotFoundError when chapter belongs to different book."""
        # Given a campaign chapter belongs to a different book
        other_book = await campaign_book_factory()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Campaign chapter not found"):
            await deps.provide_campaign_chapter_by_id(base_campaign_chapter.id, other_book)


class TestProvideCharacterByIdAndCompany:
    """Test provide_character_by_id_and_company dependency."""

    async def test_returns_character_when_found(
        self, base_company: Company, base_character: Character
    ) -> None:
        """Verify returning a character when found by ID and company."""
        # Given a character exists (from fixture)
        # When we provide the character by ID
        result = await deps.provide_character_by_id_and_company(base_character.id, base_company)

        # Then the character is returned
        assert result.id == base_character.id

    async def test_raises_not_found_when_missing(self, base_company: Company) -> None:
        """Verify raising NotFoundError when character does not exist."""
        # Given a non-existent character ID
        non_existent_id = PydanticObjectId()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Character not found"):
            await deps.provide_character_by_id_and_company(non_existent_id, base_company)

    async def test_raises_not_found_when_wrong_company(
        self, base_character: Character, company_factory: Callable[..., Company]
    ) -> None:
        """Verify raising NotFoundError when character belongs to different company."""
        # Given a character belongs to a different company
        other_company = await company_factory()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Character not found"):
            await deps.provide_character_by_id_and_company(base_character.id, other_company)


class TestProvideCharacterTraitById:
    """Test provide_character_trait_by_id dependency."""

    async def test_returns_character_trait_when_found_by_character_trait_id(
        self,
        base_character: Character,
        character_trait_factory: Callable[..., CharacterTrait],
    ) -> None:
        """Verify returning a character trait when found by CharacterTrait ID."""
        # Given a character trait exists
        character_trait = await character_trait_factory(character_id=base_character.id)

        # When we provide the character trait by its ID
        result = await deps.provide_character_trait_by_id(character_trait.id, base_character.id)

        # Then the character trait is returned
        assert result.id == character_trait.id

    async def test_returns_character_trait_when_found_by_trait_id(
        self,
        base_character: Character,
        trait_factory: Callable[..., Trait],
        character_trait_factory: Callable[..., CharacterTrait],
    ) -> None:
        """Verify returning a character trait when found by Trait ID fallback."""
        # Given a trait and character trait exist
        trait = await trait_factory()
        character_trait = await character_trait_factory(character_id=base_character.id, trait=trait)

        # When we provide using the trait's ID (not character_trait's ID)
        result = await deps.provide_character_trait_by_id(trait.id, base_character.id)

        # Then the character trait is returned via fallback lookup
        assert result.id == character_trait.id

    async def test_raises_not_found_when_missing(self, base_character: Character) -> None:
        """Verify raising NotFoundError when character trait does not exist."""
        # Given a non-existent character trait ID
        non_existent_id = PydanticObjectId()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Character trait not found"):
            await deps.provide_character_trait_by_id(non_existent_id, base_character.id)


class TestProvideInventoryItemById:
    """Test provide_inventory_item_by_id dependency."""

    async def test_returns_inventory_item_when_found(
        self, base_character: Character, inventory_item_factory: Callable[..., CharacterInventory]
    ) -> None:
        """Verify returning an inventory item when found by ID."""
        # Given an inventory item exists
        item = await inventory_item_factory(
            character_id=base_character.id,
            name="Test Item",
            description="Test description",
            type=InventoryItemType.EQUIPMENT,
        )

        # When we provide the item by ID
        result = await deps.provide_inventory_item_by_id(item.id)

        # Then the item is returned
        assert result.id == item.id

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when inventory item does not exist."""
        # Given a non-existent item ID
        non_existent_id = PydanticObjectId()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Inventory item not found"):
            await deps.provide_inventory_item_by_id(non_existent_id)

    async def test_raises_not_found_when_archived(
        self, base_character: Character, inventory_item_factory: Callable[..., CharacterInventory]
    ) -> None:
        """Verify raising NotFoundError when inventory item is archived."""
        # Given an archived inventory item exists
        item = await inventory_item_factory(
            character_id=base_character.id,
            name="Archived Item",
            description="Test description",
            type=InventoryItemType.EQUIPMENT,
            is_archived=True,
        )

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Inventory item not found"):
            await deps.provide_inventory_item_by_id(item.id)


class TestProvideNoteById:
    """Test provide_note_by_id dependency."""

    async def test_returns_note_when_found(
        self,
        base_character: Character,
        base_company: Company,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify returning a note when found by ID."""
        # Given a note exists
        note = await note_factory(
            title="Test Note",
            content="Test content for the note",
            character_id=base_character.id,
            company_id=base_company.id,
        )

        # When we provide the note by ID
        result = await deps.provide_note_by_id(note.id)

        # Then the note is returned
        assert result.id == note.id

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when note does not exist."""
        # Given a non-existent note ID
        non_existent_id = PydanticObjectId()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Note not found"):
            await deps.provide_note_by_id(non_existent_id)

    async def test_raises_not_found_when_archived(
        self, base_character: Character, base_company: Company, note_factory: Callable[..., Note]
    ) -> None:
        """Verify raising NotFoundError when note is archived."""
        # Given an archived note exists
        note = await note_factory(
            title="Archived Note",
            content="Archived content for the note",
            character_id=base_character.id,
            company_id=base_company.id,
            is_archived=True,
        )

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Note not found"):
            await deps.provide_note_by_id(note.id)


class TestProvidePgNoteById:
    """Test pg_deps.provide_note_by_id Tortoise dependency."""

    async def test_returns_note_when_found(
        self,
        pg_note_factory: Callable[..., PgNote],
        pg_company_factory: Callable,
    ) -> None:
        """Verify returning a Tortoise note when found by ID."""
        # Given a Tortoise note exists
        company = await pg_company_factory()
        note = await pg_note_factory(
            title="Test Note",
            content="Test content for the note",
            company=company,
        )

        # When we provide the note by ID
        result = await pg_deps.provide_note_by_id(note.id)

        # Then the note is returned
        assert str(result.id) == str(note.id)

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when Tortoise note does not exist."""
        from uuid import uuid4

        with pytest.raises(NotFoundError, match="Note not found"):
            await pg_deps.provide_note_by_id(uuid4())

    async def test_raises_not_found_when_archived(
        self,
        pg_note_factory: Callable[..., PgNote],
        pg_company_factory: Callable,
    ) -> None:
        """Verify raising NotFoundError when Tortoise note is archived."""
        # Given an archived Tortoise note
        company = await pg_company_factory()
        note = await pg_note_factory(
            title="Archived Note",
            content="Archived content",
            company=company,
            is_archived=True,
        )

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Note not found"):
            await pg_deps.provide_note_by_id(note.id)


class TestProvideQuickrollById:
    """Test provide_quickroll_by_id dependency."""

    async def test_returns_quickroll_when_found(
        self, quickroll_factory: Callable[..., QuickRoll]
    ) -> None:
        """Verify returning a quick roll when found by ID."""
        # Given a quick roll exists
        quickroll = await quickroll_factory()

        # When we provide the quick roll by ID
        result = await deps.provide_quickroll_by_id(quickroll.id)

        # Then the quick roll is returned
        assert result.id == quickroll.id

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when quick roll does not exist."""
        # Given a non-existent quick roll ID
        non_existent_id = PydanticObjectId()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Quick roll not found"):
            await deps.provide_quickroll_by_id(non_existent_id)

    async def test_raises_not_found_when_archived(
        self, quickroll_factory: Callable[..., QuickRoll]
    ) -> None:
        """Verify raising NotFoundError when quick roll is archived."""
        # Given an archived quick roll exists
        quickroll = await quickroll_factory(is_archived=True)

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Quick roll not found"):
            await deps.provide_quickroll_by_id(quickroll.id)


class TestProvidePgQuickrollById:
    """Test pg_deps.provide_quickroll_by_id Tortoise dependency."""

    async def test_returns_quickroll_when_found(
        self,
        pg_quickroll_factory: Callable[..., PgQuickRoll],
        pg_company_factory: Callable,
        pg_user_factory: Callable,
    ) -> None:
        """Verify returning a Tortoise quick roll when found by ID."""
        # Given a Tortoise quick roll exists
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        quickroll = await pg_quickroll_factory(user=user)

        # When we provide the quick roll by ID
        result = await pg_deps.provide_quickroll_by_id(quickroll.id)

        # Then the quick roll is returned with traits prefetched
        assert str(result.id) == str(quickroll.id)

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when Tortoise quick roll does not exist."""
        from uuid import uuid4

        with pytest.raises(NotFoundError, match="Quick roll not found"):
            await pg_deps.provide_quickroll_by_id(uuid4())

    async def test_raises_not_found_when_archived(
        self,
        pg_quickroll_factory: Callable[..., PgQuickRoll],
        pg_company_factory: Callable,
        pg_user_factory: Callable,
    ) -> None:
        """Verify raising NotFoundError when Tortoise quick roll is archived."""
        # Given an archived Tortoise quick roll
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        quickroll = await pg_quickroll_factory(user=user, is_archived=True)

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Quick roll not found"):
            await pg_deps.provide_quickroll_by_id(quickroll.id)


class TestProvideTraitCategoryById:
    """Test provide_trait_category_by_id dependency."""

    async def test_returns_trait_category_when_found(self) -> None:
        """Verify returning a trait category when found by ID."""
        # Given a trait category exists (from bootstrap)
        category = await TraitCategory.find_one(TraitCategory.is_archived == False)
        assert category is not None

        # When we provide the category by ID
        result = await deps.provide_trait_category_by_id(category.id)

        # Then the category is returned
        assert result.id == category.id

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when trait category does not exist."""
        # Given a non-existent category ID
        non_existent_id = PydanticObjectId()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Trait category not found"):
            await deps.provide_trait_category_by_id(non_existent_id)


class TestProvideUserByIdAndCompany:
    """Test provide_user_by_id_and_company dependency."""

    async def test_returns_user_when_found(self, base_company: Company, base_user: User) -> None:
        """Verify returning a user when found by ID and company."""
        # Given a user exists (from fixture)
        # When we provide the user by ID
        result = await deps.provide_user_by_id_and_company(base_user.id, base_company)

        # Then the user is returned
        assert result.id == base_user.id

    async def test_raises_not_found_when_missing(self, base_company: Company) -> None:
        """Verify raising NotFoundError when user does not exist."""
        # Given a non-existent user ID
        non_existent_id = PydanticObjectId()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="User not found"):
            await deps.provide_user_by_id_and_company(non_existent_id, base_company)

    async def test_raises_not_found_when_wrong_company(
        self, base_user: User, company_factory: Callable[..., Company]
    ) -> None:
        """Verify raising NotFoundError when user belongs to different company."""
        # Given a user belongs to a different company
        other_company = await company_factory()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="User not found"):
            await deps.provide_user_by_id_and_company(base_user.id, other_company)


class TestProvideUserById:
    """Test provide_user_by_id dependency."""

    async def test_returns_user_when_found(self, base_user: User) -> None:
        """Verify returning a user when found by ID."""
        # Given a user exists (from fixture)
        # When we provide the user by ID
        result = await deps.provide_user_by_id(base_user.id)

        # Then the user is returned
        assert result.id == base_user.id

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when user does not exist."""
        # Given a non-existent user ID
        non_existent_id = PydanticObjectId()

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="User not found"):
            await deps.provide_user_by_id(non_existent_id)

    async def test_raises_not_found_when_archived(self, user_factory: Callable[..., User]) -> None:
        """Verify raising NotFoundError when user is archived."""
        # Given an archived user exists
        user = await user_factory(is_archived=True)

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="User not found"):
            await deps.provide_user_by_id(user.id)
