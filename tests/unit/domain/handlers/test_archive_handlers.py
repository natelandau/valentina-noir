"""Test the archive handlers (Tortoise-based)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.constants import CharacterType, SpecialtyType
from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.character import (
    Character,
    CharacterInventory,
    CharacterTrait,
    Specialty,
    VampireAttributes,
)
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import Trait, TraitPower
from vapi.db.sql_models.company import Company, CompanySettings
from vapi.db.sql_models.diceroll import DiceRoll
from vapi.db.sql_models.dictionary import DictionaryTerm
from vapi.db.sql_models.notes import Note
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import CampaignExperience, User
from vapi.domain.handlers import (
    CampaignArchiveHandler,
    CharacterArchiveHandler,
    UserArchiveHandler,
    archive_book,
    archive_campaign,
    archive_chapter,
    archive_character,
    archive_company,
    archive_user,
    cascade_archive_user,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture
    from tortoise.models import Model

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
        character_factory: Callable[..., Character],
        note_factory: Callable[..., Note],
        campaign_experience_factory: Callable[..., CampaignExperience],
        diceroll_factory: Callable[..., DiceRoll],
    ) -> None:
        """Verify archiving a campaign archives its full subtree and nothing else."""
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
        character = await character_factory(
            company=company, user_player=uploader, user_creator=uploader, campaign=campaign
        )
        campaign_note = await note_factory(company=company, campaign=campaign)
        experience = await campaign_experience_factory(user=uploader, campaign=campaign)
        # Dice rolls are historical artifacts and must survive a campaign archive (D4)
        dice_roll = await diceroll_factory(
            company=company, user=uploader, campaign=campaign, is_archived=False
        )

        # and objects that should not be archived
        campaign_2 = await campaign_factory(company=company)
        campaign_book_2 = await campaign_book_factory(campaign=campaign_2)
        campaign_chapter_2 = await campaign_chapter_factory(book=campaign_book_2)
        s3_asset_4 = await s3asset_factory(company=company, uploaded_by=uploader)
        s3_asset_5 = await s3asset_factory(company=company, uploaded_by=uploader)
        s3_asset_6 = await s3asset_factory(company=company, uploaded_by=uploader)

        # When we archive the campaign
        await archive_campaign(campaign=campaign)

        # Then the campaign and its children should be archived
        for obj, model in [
            (campaign, Campaign),
            (campaign_book, CampaignBook),
            (campaign_chapter, CampaignChapter),
            (s3_asset, S3Asset),
            (s3_asset_2, S3Asset),
            (s3_asset_3, S3Asset),
            (character, Character),
            (campaign_note, Note),
            (experience, CampaignExperience),
        ]:
            refreshed = await model.get(id=obj.id)
            assert refreshed.is_archived

        # And the dice roll survives (D4)
        assert not (await DiceRoll.get(id=dice_roll.id)).is_archived

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

    async def test_archiving_campaign_archives_only_its_own_characters(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
        campaign_factory: Callable[..., Campaign],
        character_factory: Callable[..., Character],
    ) -> None:
        """Verify archiving a campaign archives its characters but not another campaign's (D1)."""
        # Given two campaigns each with a character
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company)
        other_campaign = await campaign_factory(company=company)
        character = await character_factory(
            company=company, user_player=user, user_creator=user, campaign=campaign
        )
        other_character = await character_factory(
            company=company, user_player=user, user_creator=user, campaign=other_campaign
        )

        # When we archive the first campaign
        await archive_campaign(campaign=campaign)

        # Then its character is archived and the other campaign's character is not
        assert (await Character.get(id=character.id)).is_archived
        assert not (await Character.get(id=other_character.id)).is_archived


class TestChapterArchiveHandler:
    """Test archiving a chapter."""

    async def test_archiving_chapter_leaves_associated_characters_intact(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        campaign_chapter_factory: Callable[..., CampaignChapter],
        character_factory: Callable[..., Character],
    ) -> None:
        """Verify archiving a chapter does not cascade-archive its associated characters."""
        # Given a chapter with a character associated via the chapters<->characters M2M
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(campaign=campaign)
        chapter = await campaign_chapter_factory(book=book)
        character = await character_factory(
            company=company, user_player=user, user_creator=user, campaign=campaign
        )
        await chapter.characters.add(character)

        # When we archive the chapter
        await archive_chapter(chapter=chapter)

        # Then the chapter is archived but the associated character survives
        assert (await CampaignChapter.get(id=chapter.id)).is_archived
        assert not (await Character.get(id=character.id)).is_archived


class TestBookArchiveHandler:
    """Test archiving a book."""

    async def test_archiving_book_leaves_associated_characters_intact(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        campaign_chapter_factory: Callable[..., CampaignChapter],
        character_factory: Callable[..., Character],
    ) -> None:
        """Verify archiving a book does not cascade-archive its chapters' associated characters."""
        # Given a book whose chapter has a character associated via the M2M
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(campaign=campaign)
        chapter = await campaign_chapter_factory(book=book)
        character = await character_factory(
            company=company, user_player=user, user_creator=user, campaign=campaign
        )
        await chapter.characters.add(character)

        # When we archive the book
        await archive_book(book=book)

        # Then the book and its chapter are archived but the associated character survives
        assert (await CampaignBook.get(id=book.id)).is_archived
        assert (await CampaignChapter.get(id=chapter.id)).is_archived
        assert not (await Character.get(id=character.id)).is_archived


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
        specialty_factory: Callable[..., Specialty],
        character_trait_factory: Callable[..., CharacterTrait],
        vampire_attributes_factory: Callable[..., VampireAttributes],
        note_factory: Callable[..., Note],
        diceroll_factory: Callable[..., DiceRoll],
    ) -> None:
        """Verify archiving a character archives all it owns except dice rolls."""
        # Given objects that should be archived
        company = await company_factory()
        uploader = await user_factory(company=company)
        character = await character_factory(
            company=company, user_player=uploader, user_creator=uploader
        )
        trait = await trait_factory(custom_for_character_id=character.id)
        inventory_item = await character_inventory_factory(character=character)
        s3_asset = await s3asset_factory(company=company, uploaded_by=uploader, character=character)
        specialty = await specialty_factory(character=character, type=SpecialtyType.ACTION)
        character_trait = await character_trait_factory(character=character)
        vampire_attrs = await vampire_attributes_factory(character=character)
        character_note = await note_factory(company=company, character=character)
        # Dice rolls are historical artifacts and must survive a character archive (D4)
        dice_roll = await diceroll_factory(
            company=company, user=uploader, character=character, is_archived=False
        )

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
        await archive_character(character=character)

        # Then the character and its children should be archived
        for obj, model in [
            (character, Character),
            (trait, Trait),
            (inventory_item, CharacterInventory),
            (s3_asset, S3Asset),
            (specialty, Specialty),
            (character_trait, CharacterTrait),
            (vampire_attrs, VampireAttributes),
            (character_note, Note),
        ]:
            refreshed = await model.get(id=obj.id)
            assert refreshed.is_archived

        # And the dice roll survives (D4)
        assert not (await DiceRoll.get(id=dice_roll.id)).is_archived

        # And unrelated objects should not be archived
        for obj, model in [
            (character_2, Character),
            (trait_2, Trait),
            (inventory_item_2, CharacterInventory),
            (s3_asset_2, S3Asset),
        ]:
            refreshed = await model.get(id=obj.id)
            assert not refreshed.is_archived

    async def test_archiving_character_shares_one_batch_id(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        specialty_factory: Callable[..., Specialty],
        character_trait_factory: Callable[..., CharacterTrait],
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify every row archived by one action shares the returned batch id and a date."""
        # Given a character with several owned rows
        company = await company_factory()
        user = await user_factory(company=company)
        character = await character_factory(company=company, user_player=user, user_creator=user)
        specialty = await specialty_factory(character=character, type=SpecialtyType.ACTION)
        character_trait = await character_trait_factory(character=character)
        character_note = await note_factory(company=company, character=character)

        # When we archive the character
        ctx = await archive_character(character=character)

        # Then every archived row carries the same batch id and a non-null date
        for obj, model in [
            (character, Character),
            (specialty, Specialty),
            (character_trait, CharacterTrait),
            (character_note, Note),
        ]:
            refreshed = await model.get(id=obj.id)
            assert refreshed.archive_batch_id == ctx.batch_id
            assert refreshed.archive_date is not None

    async def test_archiving_character_archives_its_custom_trait_powers(
        self,
        character_factory: Callable[..., Character],
        trait_factory: Callable[..., Trait],
        trait_power_factory: Callable[..., TraitPower],
    ) -> None:
        """Verify a custom trait's powers are archived alongside the trait itself."""
        # Given a character whose custom trait grants a power
        character = await character_factory()
        custom_trait = await trait_factory(is_custom=True, custom_for_character_id=character.id)
        power = await trait_power_factory(trait=custom_trait, level=1, name="Custom Power")

        # And a global trait whose power belongs to nobody
        global_trait = await trait_factory()
        global_power = await trait_power_factory(trait=global_trait, level=1, name="Global Power")

        # When we archive the character
        ctx = await archive_character(character=character)

        # Then the custom trait's power is archived under the same batch
        refreshed = await TraitPower.get(id=power.id)
        assert refreshed.is_archived
        assert refreshed.archive_batch_id == ctx.batch_id

        # And the global trait's power is untouched
        assert not (await TraitPower.get(id=global_power.id)).is_archived


class TestUserArchiveHandler:
    """Test the UserArchiveHandler."""

    async def test_cascade_archive_user_rejects_unarchived_user(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify cascading a user whose row was not archived first raises rather than corrupting the batch."""
        # Given an active user (no archive_batch_id minted yet)
        company = await company_factory()
        user = await user_factory(company=company, is_archived=False)

        # When cascade_archive_user is called without archiving the user row first
        # Then it raises rather than stamping children with a NULL batch
        with pytest.raises(ValueError, match="archived first"):
            await cascade_archive_user(user)

    async def test_handle(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        s3asset_factory: Callable[..., S3Asset],
        quickroll_factory: Callable[..., QuickRoll],
        campaign_factory: Callable[..., Campaign],
        campaign_experience_factory: Callable[..., CampaignExperience],
        note_factory: Callable[..., Note],
        diceroll_factory: Callable[..., DiceRoll],
    ) -> None:
        """Verify archiving a user archives all they own except dice rolls."""
        # Given objects that should be archived
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company)
        character = await character_factory(company=company, user_player=user, user_creator=user)
        quickroll = await quickroll_factory(user=user)
        s3_asset = await s3asset_factory(company=company, uploaded_by=user, user_parent=user)
        s3_asset_2 = await s3asset_factory(company=company, uploaded_by=user, character=character)
        user_note = await note_factory(company=company, user=user)
        experience = await campaign_experience_factory(user=user, campaign=campaign)
        # Dice rolls are historical artifacts and must survive a user archive (D4)
        dice_roll = await diceroll_factory(company=company, user=user, is_archived=False)

        # And objects that should not be archived
        user_2 = await user_factory(company=company)
        character_2 = await character_factory(
            company=company, user_player=user_2, user_creator=user_2
        )
        quickroll_2 = await quickroll_factory(user=user_2)
        s3_asset_3 = await s3asset_factory(company=company, uploaded_by=user_2, user_parent=user_2)

        # When we archive the user
        await archive_user(user=user)

        # Then the user and their owned data should be archived
        for obj, model in [
            (user, User),
            (character, Character),
            (quickroll, QuickRoll),
            (s3_asset, S3Asset),
            (s3_asset_2, S3Asset),
            (user_note, Note),
            (experience, CampaignExperience),
        ]:
            refreshed = await model.get(id=obj.id)
            assert refreshed.is_archived

        # And the dice roll survives (D4)
        assert not (await DiceRoll.get(id=dice_roll.id)).is_archived

        # And unrelated objects should not be archived
        for obj, model in [
            (user_2, User),
            (character_2, Character),
            (quickroll_2, QuickRoll),
            (s3_asset_3, S3Asset),
        ]:
            refreshed = await model.get(id=obj.id)
            assert not refreshed.is_archived

    async def test_archiving_user_leaves_their_npcs_intact(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
    ) -> None:
        """Verify archiving a user archives their player characters but not their NPCs."""
        # Given a user with a PLAYER character and an NPC they created
        company = await company_factory()
        user = await user_factory(company=company)
        player_character = await character_factory(
            company=company,
            user_player=user,
            user_creator=user,
            type=CharacterType.PLAYER,
        )
        npc = await character_factory(
            company=company,
            user_creator=user,
            type=CharacterType.NPC,
            # user_player defaults to None for NPC type via the factory
        )

        # When the user is archived
        await archive_user(user=user)

        # Then the player character is archived but the NPC is not
        # (UserArchiveHandler filters by user_player_id, which is None for NPCs)
        refreshed_pc = await Character.get(id=player_character.id)
        refreshed_npc = await Character.get(id=npc.id)
        assert refreshed_pc.is_archived is True
        assert refreshed_npc.is_archived is False


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
        """Verify archiving a company archives its whole tenant under one batch id."""
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
        await archive_company(company=company)

        # Then the company and its tenant should be archived (dice rolls included for company)
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

        # And another company's data should not be archived
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

        # And the spies should each have been called (a character can be reached up to
        # three ways under D1: company loop, user cascade, campaign cascade, all idempotent)
        user_spy.assert_called()
        character_spy.assert_called()
        campaign_spy.assert_called()

        # And the company's settings row should be archived under the company batch
        settings = await CompanySettings.get(company_id=company.id)
        assert settings.is_archived
        assert settings.archive_batch_id == (await Company.get(id=company.id)).archive_batch_id

        # And another company's settings should not be archived
        settings_2 = await CompanySettings.get(company_id=company_2.id)
        assert not settings_2.is_archived

        # And the company row and a representative character share one batch id
        assert (await Character.get(id=character.id)).archive_batch_id == (
            await Company.get(id=company.id)
        ).archive_batch_id

    async def test_archive_company_rolls_back_on_midway_failure(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
        campaign_factory: Callable[..., Campaign],
        note_factory: Callable[..., Note],
        mocker: MockerFixture,
    ) -> None:
        """Verify a failure partway through a company archive rolls back every flip."""
        # Given an active company with an active user, campaign, and note
        company = await company_factory()
        user = await user_factory(company=company, is_archived=False)
        campaign = await campaign_factory(company=company, is_archived=False)
        note = await note_factory(company=company, is_archived=False)

        # And an injection point: the real _archive_where runs for every model
        # except Company (the final flip), where it raises. By the time the cascade
        # reaches the Company flip, the campaign/user/note rows have already been
        # flipped inside the transaction, so the raise must revert all of them.
        from vapi.domain.handlers import archive_handlers

        real_archive_where = archive_handlers._archive_where
        flipped_models: list[type[Model]] = []

        async def _raise_on_company(model, ctx, **filters) -> int:
            if model is Company:
                msg = "boom"
                raise RuntimeError(msg)
            flipped_models.append(model)
            return await real_archive_where(model, ctx, **filters)

        mocker.patch.object(
            archive_handlers, "_archive_where", side_effect=_raise_on_company, autospec=True
        )

        # When we archive the company
        with pytest.raises(RuntimeError, match="boom"):
            await archive_company(company=company)

        # Then real rows were flipped before the failure (guards against the cascade
        # being reordered to flip Company first, which would make this test pass
        # vacuously), and the transaction rolled every one of them back
        assert flipped_models  # at least one non-Company flip happened pre-failure
        assert (await Company.get(id=company.id)).is_archived is False
        assert (await Campaign.get(id=campaign.id)).is_archived is False
        assert (await User.get(id=user.id)).is_archived is False
        assert (await Note.get(id=note.id)).is_archived is False
