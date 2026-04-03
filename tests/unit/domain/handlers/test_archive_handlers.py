"""Test the archive handlers (Tortoise-based)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.character import Character, CharacterInventory
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.diceroll import DiceRoll
from vapi.db.sql_models.dictionary import DictionaryTerm
from vapi.db.sql_models.notes import Note
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import User
from vapi.domain.handlers import (
    CampaignArchiveHandler,
    CharacterArchiveHandler,
    CompanyArchiveHandler,
    UserArchiveHandler,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


class TestCampaignArchiveHandler:
    """Test the CampaignArchiveHandler."""

    async def test_handle(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        campaign_chapter_factory: Callable[..., CampaignChapter],
        s3asset_factory: Callable[..., S3Asset],
        debug: Callable[[...], None],
    ) -> None:
        """Test the handle method."""
        # Given objects that should be archived
        company = await company_factory()
        uploader = await user_factory(company=company)
        campaign = await campaign_factory(company=company)
        campaign_book = await campaign_book_factory(campaign=campaign)
        campaign_chapter = await campaign_chapter_factory(book=campaign_book)
        s3_asset = await s3asset_factory(company=company, uploaded_by=uploader, campaign=campaign)
        s3_asset_2 = await s3asset_factory(
            company=company, uploaded_by=uploader, book=campaign_book
        )
        s3_asset_3 = await s3asset_factory(
            company=company, uploaded_by=uploader, chapter=campaign_chapter
        )

        # and objects that should not be archived
        campaign_2 = await campaign_factory(company=company)
        campaign_book_2 = await campaign_book_factory(campaign=campaign_2)
        campaign_chapter_2 = await campaign_chapter_factory(book=campaign_book_2)
        s3_asset_4 = await s3asset_factory(company=company, uploaded_by=uploader)
        s3_asset_5 = await s3asset_factory(company=company, uploaded_by=uploader)
        s3_asset_6 = await s3asset_factory(company=company, uploaded_by=uploader)

        # When we archive the campaign
        handler = CampaignArchiveHandler(campaign=campaign)
        await handler.handle()

        # Then the campaign and its children should be archived
        for obj, model in [
            (campaign, Campaign),
            (campaign_book, CampaignBook),
            (campaign_chapter, CampaignChapter),
            (s3_asset, S3Asset),
            (s3_asset_2, S3Asset),
            (s3_asset_3, S3Asset),
        ]:
            refreshed = await model.get(id=obj.id)
            assert refreshed.is_archived

        # And unrelated objects should not be archived
        for obj, model in [
            (campaign_2, Campaign),
            (campaign_book_2, CampaignBook),
            (campaign_chapter_2, CampaignChapter),
            (s3_asset_4, S3Asset),
            (s3_asset_5, S3Asset),
            (s3_asset_6, S3Asset),
        ]:
            refreshed = await model.get(id=obj.id)
            assert not refreshed.is_archived


class TestCharacterArchiveHandler:
    """Test the CharacterArchiveHandler."""

    async def test_handle(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        trait_factory: Callable[..., Trait],
        character_inventory_factory: Callable[..., CharacterInventory],
        s3asset_factory: Callable[..., S3Asset],
    ) -> None:
        """Test the handle method."""
        # Given objects that should be archived
        company = await company_factory()
        uploader = await user_factory(company=company)
        character = await character_factory(
            company=company, user_player=uploader, user_creator=uploader
        )
        trait = await trait_factory(custom_for_character_id=character.id)
        inventory_item = await character_inventory_factory(character=character)
        s3_asset = await s3asset_factory(company=company, uploaded_by=uploader, character=character)

        # And objects that should not be archived
        uploader_2 = await user_factory(company=company)
        character_2 = await character_factory(
            company=company, user_player=uploader_2, user_creator=uploader_2
        )
        trait_2 = await trait_factory(custom_for_character_id=character_2.id)
        inventory_item_2 = await character_inventory_factory(character=character_2)
        s3_asset_2 = await s3asset_factory(
            company=company, uploaded_by=uploader_2, character=character_2
        )

        # When we archive the character
        handler = CharacterArchiveHandler(character=character)
        await handler.handle()

        for obj, model in [
            (character, Character),
            (trait, Trait),
            (inventory_item, CharacterInventory),
            (s3_asset, S3Asset),
        ]:
            refreshed = await model.get(id=obj.id)
            assert refreshed.is_archived

        for obj, model in [
            (character_2, Character),
            (trait_2, Trait),
            (inventory_item_2, CharacterInventory),
            (s3_asset_2, S3Asset),
        ]:
            refreshed = await model.get(id=obj.id)
            assert not refreshed.is_archived


class TestUserArchiveHandler:
    """Test the UserArchiveHandler."""

    async def test_handle(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        s3asset_factory: Callable[..., S3Asset],
        quickroll_factory: Callable[..., QuickRoll],
    ) -> None:
        """Test the handle method."""
        # Given objects that should be archived
        company = await company_factory()
        user = await user_factory(company=company)
        character = await character_factory(company=company, user_player=user, user_creator=user)
        quickroll = await quickroll_factory(user=user)
        s3_asset = await s3asset_factory(company=company, uploaded_by=user, user_parent=user)
        s3_asset_2 = await s3asset_factory(company=company, uploaded_by=user, character=character)

        # And objects that should not be archived
        user_2 = await user_factory(company=company)
        character_2 = await character_factory(
            company=company, user_player=user_2, user_creator=user_2
        )
        quickroll_2 = await quickroll_factory(user=user_2)
        s3_asset_3 = await s3asset_factory(company=company, uploaded_by=user_2, user_parent=user_2)

        # When we archive the user
        handler = UserArchiveHandler(user=user)
        await handler.handle()

        for obj, model in [
            (user, User),
            (character, Character),
            (quickroll, QuickRoll),
            (s3_asset, S3Asset),
            (s3_asset_2, S3Asset),
        ]:
            refreshed = await model.get(id=obj.id)
            assert refreshed.is_archived

        for obj, model in [
            (user_2, User),
            (character_2, Character),
            (quickroll_2, QuickRoll),
            (s3_asset_3, S3Asset),
        ]:
            refreshed = await model.get(id=obj.id)
            assert not refreshed.is_archived


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
        diceroll_factory: Callable[..., DiceRoll],
        mocker: MockerFixture,
    ) -> None:
        """Test the handle method."""
        # Given objects that should be archived
        company = await company_factory()
        user = await user_factory(company=company, is_archived=False)
        campaign = await campaign_factory(company=company, is_archived=False)
        character = await character_factory(
            company=company,
            user_player=user,
            user_creator=user,
            campaign=campaign,
            is_archived=False,
        )
        s3_asset = await s3asset_factory(company=company, uploaded_by=user, is_archived=False)
        note = await note_factory(company=company, is_archived=False)
        dictionary_term = await dictionary_term_factory(company_id=company.id, is_archived=False)
        character_concept = await character_concept_factory(
            company_id=company.id, is_archived=False
        )
        dice_roll = await diceroll_factory(company=company, user=user, is_archived=False)

        # And objects that should not be archived
        company_2 = await company_factory()
        user_2 = await user_factory(company=company_2)
        character_2 = await character_factory(
            company=company_2, user_player=user_2, user_creator=user_2
        )
        s3_asset_2 = await s3asset_factory(company=company_2, uploaded_by=user_2)
        note_2 = await note_factory(company=company_2)
        dictionary_term_2 = await dictionary_term_factory(company_id=company_2.id)
        character_concept_2 = await character_concept_factory(company_id=company_2.id)
        dice_roll_2 = await diceroll_factory(company=company_2, user=user_2)

        # and setup spies
        user_spy = mocker.spy(UserArchiveHandler, "handle")
        character_spy = mocker.spy(CharacterArchiveHandler, "handle")
        campaign_spy = mocker.spy(CampaignArchiveHandler, "handle")

        # When we archive the company
        handler = CompanyArchiveHandler(company=company)
        await handler.handle()

        for obj, model in [
            (company, Company),
            (campaign, Campaign),
            (user, User),
            (character, Character),
            (s3_asset, S3Asset),
            (note, Note),
            (dictionary_term, DictionaryTerm),
            (character_concept, CharacterConcept),
            (dice_roll, DiceRoll),
        ]:
            refreshed = await model.get(id=obj.id)
            assert refreshed.is_archived

        for obj, model in [
            (company_2, Company),
            (user_2, User),
            (character_2, Character),
            (s3_asset_2, S3Asset),
            (note_2, Note),
            (dictionary_term_2, DictionaryTerm),
            (character_concept_2, CharacterConcept),
            (dice_roll_2, DiceRoll),
        ]:
            refreshed = await model.get(id=obj.id)
            assert not refreshed.is_archived

        # Then the spies should have been called
        user_spy.assert_called_once()
        # Character handler is called twice: once from UserArchiveHandler cascade,
        # once from CompanyArchiveHandler iterating company characters
        assert character_spy.call_count == 2
        campaign_spy.assert_called_once()
