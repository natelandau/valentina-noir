"""Test the CompanyArchiver handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from beanie import PydanticObjectId

from vapi.constants import AssetParentType
from vapi.domain.handlers import (
    CampaignArchiveHandler,
    CharacterArchiveHandler,
    CompanyArchiveHandler,
    UserArchiveHandler,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

    from vapi.db.models import (
        Campaign,
        CampaignBook,
        CampaignChapter,
        Character,
        CharacterConcept,
        CharacterInventory,
        Company,
        DiceRoll,
        DictionaryTerm,
        Note,
        QuickRoll,
        S3Asset,
        Trait,
        User,
    )

pytestmark = pytest.mark.anyio


class TestCampaignArchiveHandler:
    """Test the CampaignArchiveHandler."""

    async def test_handle(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        campaign_chapter_factory: Callable[..., CampaignChapter],
        s3asset_factory: Callable[..., S3Asset],
        debug: Callable[[...], None],
    ) -> None:
        """Test the handle method."""
        # Given objects that should be archived
        company = await company_factory()
        campaign = await campaign_factory(company_id=company.id)
        campaign_book = await campaign_book_factory(campaign_id=campaign.id)
        campaign_chapter = await campaign_chapter_factory(book_id=campaign_book.id)
        s3_asset = await s3asset_factory(
            parent_type=AssetParentType.CAMPAIGN, parent_id=campaign.id
        )
        s3_asset_2 = await s3asset_factory(
            parent_type=AssetParentType.CAMPAIGN_BOOK, parent_id=campaign_book.id
        )
        s3_asset_3 = await s3asset_factory(
            parent_type=AssetParentType.CAMPAIGN_CHAPTER, parent_id=campaign_chapter.id
        )

        # and objects that should not be archived
        campaign_2 = await campaign_factory(company_id=company.id)
        campaign_book_2 = await campaign_book_factory(campaign_id=campaign_2.id)
        campaign_chapter_2 = await campaign_chapter_factory(book_id=campaign_book_2.id)
        s3_asset_4 = await s3asset_factory(
            parent_type=AssetParentType.CAMPAIGN, parent_id=PydanticObjectId()
        )
        s3_asset_5 = await s3asset_factory(
            parent_type=AssetParentType.CAMPAIGN_BOOK, parent_id=PydanticObjectId()
        )
        s3_asset_6 = await s3asset_factory(
            parent_type=AssetParentType.CAMPAIGN_CHAPTER, parent_id=PydanticObjectId()
        )

        # When we archive the company
        handler = CampaignArchiveHandler(campaign=campaign)
        await handler.handle()

        # Then the campaigns should be archived
        for item in [campaign, campaign_book, campaign_chapter, s3_asset, s3_asset_2, s3_asset_3]:
            await item.sync()
            assert item.is_archived

        for item in [
            campaign_2,
            campaign_book_2,
            campaign_chapter_2,
            s3_asset_4,
            s3_asset_5,
            s3_asset_6,
        ]:
            await item.sync()
            assert not item.is_archived


class TestCharacterArchiveHandler:
    """Test the CharacterArchiveHandler."""

    async def test_handle(
        self,
        character_factory: Callable[..., Character],
        trait_factory: Callable[..., Trait],
        inventory_item_factory: Callable[..., CharacterInventory],
        s3asset_factory: Callable[..., S3Asset],
    ) -> None:
        """Test the handle method."""
        # Given objects that should be archived
        character = await character_factory()
        trait = await trait_factory(custom_for_character_id=character.id)
        inventory_item = await inventory_item_factory(character_id=character.id)
        s3_asset = await s3asset_factory(
            parent_type=AssetParentType.CHARACTER, parent_id=character.id
        )

        # And objects that should not be archived
        character_2 = await character_factory()
        trait_2 = await trait_factory(custom_for_character_id=character_2.id)
        inventory_item_2 = await inventory_item_factory(character_id=character_2.id)
        s3_asset_2 = await s3asset_factory(
            parent_type=AssetParentType.CHARACTER, parent_id=character_2.id
        )

        # When we archive the character
        handler = CharacterArchiveHandler(character=character)
        await handler.handle()

        for item in [character, trait, inventory_item, s3_asset]:
            await item.sync()
            assert item.is_archived

        for item in [character_2, trait_2, inventory_item_2, s3_asset_2]:
            await item.sync()
            assert not item.is_archived


class TestUserArchiveHandler:
    """Test the UserArchiveHandler."""

    async def test_handle(
        self,
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        s3asset_factory: Callable[..., S3Asset],
        quickroll_factory: Callable[..., QuickRoll],
    ) -> None:
        """Test the handle method."""
        # Given objects that should be archived
        user = await user_factory(is_archived=False)
        character = await character_factory(user_player_id=user.id, is_archived=False)
        quickroll = await quickroll_factory(user_id=user.id, is_archived=False)
        s3_asset = await s3asset_factory(
            parent_type=AssetParentType.USER, parent_id=user.id, is_archived=False
        )
        s3_asset_2 = await s3asset_factory(
            parent_type=AssetParentType.CHARACTER, parent_id=character.id, is_archived=False
        )

        # And objects that should not be archived
        user_2 = await user_factory()
        character_2 = await character_factory(user_player_id=user_2.id)
        quickroll_2 = await quickroll_factory(user_id=user_2.id)
        s3_asset_3 = await s3asset_factory(parent_type=AssetParentType.USER, parent_id=user_2.id)

        # When we archive the user
        handler = UserArchiveHandler(user=user)
        await handler.handle()

        for item in [user, character, quickroll, s3_asset, s3_asset_2]:
            await item.sync()
            assert item.is_archived

        for item in [user_2, character_2, quickroll_2, s3_asset_3]:
            await item.sync()
            assert not item.is_archived


class TestCompanyArchiveHandler:
    """Test the CompanyArchiveHandler."""

    async def test_handle(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        s3asset_factory: Callable[..., S3Asset],
        campaign_factory: Callable[..., Campaign],
        note_factory: Callable[..., Note],
        dictionary_term_factory: Callable[..., DictionaryTerm],
        character_concept_factory: Callable[..., CharacterConcept],
        dice_roll_factory: Callable[..., DiceRoll],
        mocker: MockerFixture,
    ) -> None:
        """Test the handle method."""
        # Given objects that should be archived
        company = await company_factory()
        user = await user_factory(company_id=company.id, is_archived=False)
        campaign = await campaign_factory(company_id=company.id, is_archived=False)
        character = await character_factory(company_id=company.id, is_archived=False)
        s3_asset = await s3asset_factory(
            parent_type=AssetParentType.UNKNOWN,
            parent_id=None,
            company_id=company.id,
            is_archived=False,
        )
        note = await note_factory(company_id=company.id, is_archived=False)
        dictionary_term = await dictionary_term_factory(company_id=company.id, is_archived=False)
        character_concept = await character_concept_factory(
            company_id=company.id, is_archived=False
        )
        dice_roll = await dice_roll_factory(company_id=company.id, is_archived=False)

        # And objects that should not be archived
        company_2 = await company_factory()
        user_2 = await user_factory(company_id=company_2.id)
        character_2 = await character_factory(user_player_id=user_2.id)
        s3_asset_2 = await s3asset_factory(
            parent_type=AssetParentType.COMPANY, parent_id=company_2.id
        )
        note_2 = await note_factory(company_id=company_2.id)
        dictionary_term_2 = await dictionary_term_factory(company_id=company_2.id)
        character_concept_2 = await character_concept_factory(company_id=company_2.id)
        dice_roll_2 = await dice_roll_factory(company_id=company_2.id)

        # and setup spies
        user_spy = mocker.spy(UserArchiveHandler, "handle")
        character_spy = mocker.spy(CharacterArchiveHandler, "handle")
        campaign_spy = mocker.spy(CampaignArchiveHandler, "handle")

        # When we archive the company
        handler = CompanyArchiveHandler(company=company)
        await handler.handle()

        for item in [
            company,
            campaign,
            user,
            character,
            s3_asset,
            note,
            dictionary_term,
            character_concept,
            dice_roll,
        ]:
            await item.sync()
            assert item.is_archived

        for item in [
            company_2,
            user_2,
            character_2,
            s3_asset_2,
            note_2,
            dictionary_term_2,
            character_concept_2,
            dice_roll_2,
        ]:
            await item.sync()
            assert not item.is_archived

        # Then the spies should have been called
        user_spy.assert_called_once()
        character_spy.assert_called_once()
        campaign_spy.assert_called_once()
