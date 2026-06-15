"""Unit tests for campaign services."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.domain.services import CampaignService
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.sql_models.aws import S3Asset
    from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
    from vapi.db.sql_models.character import Character, Specialty
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.diceroll import DiceRoll
    from vapi.db.sql_models.notes import Note
    from vapi.db.sql_models.user import User

pytestmark = pytest.mark.anyio


class TestCampaignService:
    """Test the campaign service."""

    async def test_get_next_book_number_first_book(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
    ) -> None:
        """Verify get_next_book_number returns 1 for a campaign with no books."""
        # Given a campaign with no books
        company = await company_factory()
        campaign = await campaign_factory(company=company)

        # When the next book number is requested
        service = CampaignService()
        next_book_number = await service.get_next_book_number(campaign)

        # Then the next book number should be 1
        assert next_book_number == 1

    async def test_get_next_book_number(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
    ) -> None:
        """Verify get_next_book_number returns count + 1."""
        # Given a campaign with 3 books
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        await campaign_book_factory(campaign=campaign)
        await campaign_book_factory(campaign=campaign)
        await campaign_book_factory(campaign=campaign)

        # When the next book number is requested
        service = CampaignService()
        next_book_number = await service.get_next_book_number(campaign)

        # Then the next book number should be 4
        assert next_book_number == 4

    async def test_get_next_chapter_number_first_chapter(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
    ) -> None:
        """Verify get_next_chapter_number returns 1 for a book with no chapters."""
        # Given a book with no chapters
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(campaign=campaign)

        # When the next chapter number is requested
        service = CampaignService()
        next_chapter_number = await service.get_next_chapter_number(book)

        # Then the next chapter number should be 1
        assert next_chapter_number == 1

    async def test_get_next_chapter_number(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        campaign_chapter_factory: Callable[..., CampaignChapter],
    ) -> None:
        """Verify get_next_chapter_number returns count + 1."""
        # Given a book with 2 chapters
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(campaign=campaign)
        await campaign_chapter_factory(book=book)
        await campaign_chapter_factory(book=book)

        # When the next chapter number is requested
        service = CampaignService()
        next_chapter_number = await service.get_next_chapter_number(book)

        # Then the next chapter number should be 3
        assert next_chapter_number == 3

    async def test_renumber_books(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
    ) -> None:
        """Verify renumber_books shifts siblings correctly in both directions."""
        # Given a campaign with 4 books
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        booka = await campaign_book_factory(name="Book A", campaign=campaign)
        bookb = await campaign_book_factory(name="Book B", campaign=campaign)
        bookc = await campaign_book_factory(name="Book C", campaign=campaign)
        bookd = await campaign_book_factory(name="Book D", campaign=campaign)

        # When bookd is renumbered to 2
        service = CampaignService()
        await service.renumber_books(bookd, 2)
        await booka.refresh_from_db()
        await bookb.refresh_from_db()
        await bookc.refresh_from_db()
        await bookd.refresh_from_db()

        # Then the books should be in the following order: 1, 3, 4, 2
        assert booka.number == 1
        assert bookb.number == 3
        assert bookc.number == 4
        assert bookd.number == 2

        # When bookd is renumbered back to 4
        await service.renumber_books(bookd, 4)
        await booka.refresh_from_db()
        await bookb.refresh_from_db()
        await bookc.refresh_from_db()
        await bookd.refresh_from_db()

        # Then the books should be in the following order: 1, 2, 3, 4
        assert booka.number == 1
        assert bookb.number == 2
        assert bookc.number == 3
        assert bookd.number == 4

    @pytest.mark.parametrize(
        "target_number",
        [2, 0],
        ids=["exceeds_count", "less_than_one"],
    )
    async def test_renumber_books_invalid_number(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        target_number: int,
    ) -> None:
        """Verify renumber_books raises ValidationError for out-of-range target numbers."""
        # Given a campaign with 1 book
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(name="Book A", campaign=campaign)

        # When the book is renumbered to an invalid number
        # Then a ValidationError should be raised
        service = CampaignService()
        with pytest.raises(ValidationError):
            await service.renumber_books(book, target_number)

    async def test_renumber_chapters(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        campaign_chapter_factory: Callable[..., CampaignChapter],
    ) -> None:
        """Verify renumber_chapters shifts siblings correctly in both directions."""
        # Given a book with 4 chapters
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(campaign=campaign)
        chaptera = await campaign_chapter_factory(name="Chapter A", book=book)
        chapterb = await campaign_chapter_factory(name="Chapter B", book=book)
        chapterc = await campaign_chapter_factory(name="Chapter C", book=book)
        chapterd = await campaign_chapter_factory(name="Chapter D", book=book)

        # When chapterd is renumbered to 2
        service = CampaignService()
        await service.renumber_chapters(chapterd, 2)
        await chaptera.refresh_from_db()
        await chapterb.refresh_from_db()
        await chapterc.refresh_from_db()
        await chapterd.refresh_from_db()

        # Then the chapters should be in the following order: 1, 3, 4, 2
        assert chaptera.number == 1
        assert chapterb.number == 3
        assert chapterc.number == 4

        # When chapterd is renumbered back to 4
        await service.renumber_chapters(chapterd, 4)
        await chaptera.refresh_from_db()
        await chapterb.refresh_from_db()
        await chapterc.refresh_from_db()
        await chapterd.refresh_from_db()

        # Then the chapters should be in the following order: 1, 2, 3, 4
        assert chaptera.number == 1
        assert chapterb.number == 2
        assert chapterc.number == 3
        assert chapterd.number == 4

    @pytest.mark.parametrize(
        "target_number",
        [2, 0],
        ids=["exceeds_count", "less_than_one"],
    )
    async def test_renumber_chapters_invalid_number(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        campaign_chapter_factory: Callable[..., CampaignChapter],
        target_number: int,
    ) -> None:
        """Verify renumber_chapters raises ValidationError for out-of-range target numbers."""
        # Given a book with 1 chapter
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(campaign=campaign)
        chapter = await campaign_chapter_factory(name="Chapter A", book=book)

        # When the chapter is renumbered to an invalid number
        # Then a ValidationError should be raised
        service = CampaignService()
        with pytest.raises(ValidationError):
            await service.renumber_chapters(chapter, target_number)

    async def test_delete_book_and_renumber_one_book(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
    ) -> None:
        """Verify delete_book_and_renumber soft-deletes a single book."""
        # Given a campaign with 1 book
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(name="Book A", campaign=campaign)

        # When the book is deleted
        service = CampaignService()
        await service.delete_book_and_renumber(book)
        await book.refresh_from_db()

        # Then the book should be archived
        assert book.is_archived
        assert book.number == 1

    async def test_delete_book_and_renumber_multiple_books(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
    ) -> None:
        """Verify delete_book_and_renumber shifts higher-numbered books down."""
        # Given a campaign with 4 books
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        booka = await campaign_book_factory(name="Book A", campaign=campaign, number=1)
        bookb = await campaign_book_factory(name="Book B", campaign=campaign, number=2)
        bookc = await campaign_book_factory(name="Book C", campaign=campaign, number=3)
        bookd = await campaign_book_factory(name="Book D", campaign=campaign, number=4)

        # When bookb is deleted
        service = CampaignService()
        await service.delete_book_and_renumber(bookb)
        await booka.refresh_from_db()
        await bookb.refresh_from_db()
        await bookc.refresh_from_db()
        await bookd.refresh_from_db()

        # Then the books should be renumbered: 1, archived, 2, 3
        assert booka.number == 1
        assert bookb.is_archived
        assert bookc.number == 2
        assert bookd.number == 3

    async def test_delete_chapter_and_renumber_one_chapter(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        campaign_chapter_factory: Callable[..., CampaignChapter],
    ) -> None:
        """Verify delete_chapter_and_renumber soft-deletes a single chapter."""
        # Given a book with 1 chapter
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(campaign=campaign)
        chapter = await campaign_chapter_factory(name="Chapter A", book=book)

        # When the chapter is deleted
        service = CampaignService()
        await service.delete_chapter_and_renumber(chapter)
        await chapter.refresh_from_db()

        # Then the chapter should be archived
        assert chapter.is_archived
        assert chapter.number == 1

    async def test_delete_chapter_and_renumber_multiple_chapters(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        campaign_chapter_factory: Callable[..., CampaignChapter],
    ) -> None:
        """Verify delete_chapter_and_renumber shifts higher-numbered chapters down."""
        # Given a book with 4 chapters
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(campaign=campaign)
        chaptera = await campaign_chapter_factory(name="Chapter A", book=book, number=1)
        chapterb = await campaign_chapter_factory(name="Chapter B", book=book, number=2)
        chapterc = await campaign_chapter_factory(name="Chapter C", book=book, number=3)
        chapterd = await campaign_chapter_factory(name="Chapter D", book=book, number=4)

        # When chapterb is deleted
        service = CampaignService()
        await service.delete_chapter_and_renumber(chapterb)
        await chaptera.refresh_from_db()
        await chapterb.refresh_from_db()
        await chapterc.refresh_from_db()
        await chapterd.refresh_from_db()

        # Then the chapters should be renumbered: 1, archived, 2, 3
        assert chaptera.number == 1
        assert chapterb.is_archived
        assert chapterc.number == 2
        assert chapterd.number == 3

    async def test_delete_book_cascades_to_chapters_notes_and_assets(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        campaign_chapter_factory: Callable[..., CampaignChapter],
        note_factory: Callable[..., Note],
        s3asset_factory: Callable[..., S3Asset],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify delete_book_and_renumber cascades the archive to the book's subtree under one batch."""
        # Given a book with a chapter, notes and assets on both, a sibling book, and an unrelated book
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(name="Book A", campaign=campaign, number=1)
        sibling = await campaign_book_factory(name="Book B", campaign=campaign, number=2)
        chapter = await campaign_chapter_factory(name="Chapter A", book=book, number=1)
        book_note = await note_factory(company=company, book=book)
        chapter_note = await note_factory(company=company, chapter=chapter)
        book_asset = await s3asset_factory(company=company, uploaded_by=user, book=book)
        chapter_asset = await s3asset_factory(company=company, uploaded_by=user, chapter=chapter)
        # And a chapter under a different book that must not be touched
        other_book = await campaign_book_factory(name="Other", campaign=campaign, number=3)
        other_chapter = await campaign_chapter_factory(name="Other Chapter", book=other_book)

        # When the book is deleted
        service = CampaignService()
        await service.delete_book_and_renumber(book)

        await book.refresh_from_db()
        await chapter.refresh_from_db()
        await book_note.refresh_from_db()
        await chapter_note.refresh_from_db()
        await book_asset.refresh_from_db()
        await chapter_asset.refresh_from_db()
        await sibling.refresh_from_db()
        await other_book.refresh_from_db()
        await other_chapter.refresh_from_db()

        # Then the book and its whole subtree are archived under one batch id
        assert book.is_archived
        assert chapter.is_archived
        assert book_note.is_archived
        assert chapter_note.is_archived
        assert book_asset.is_archived
        assert chapter_asset.is_archived
        assert book.archive_batch_id is not None
        assert chapter.archive_batch_id == book.archive_batch_id
        assert book_note.archive_batch_id == book.archive_batch_id
        assert chapter_note.archive_batch_id == book.archive_batch_id
        assert book_asset.archive_batch_id == book.archive_batch_id
        assert chapter_asset.archive_batch_id == book.archive_batch_id

        # And the sibling book is renumbered down while the unrelated book and its
        # chapter are untouched
        assert sibling.number == 1
        assert other_book.is_archived is False
        assert other_chapter.is_archived is False

    async def test_delete_chapter_cascades_to_notes_and_assets(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        campaign_chapter_factory: Callable[..., CampaignChapter],
        note_factory: Callable[..., Note],
        s3asset_factory: Callable[..., S3Asset],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify delete_chapter_and_renumber cascades the archive to the chapter's note and asset."""
        # Given a chapter with a note and an asset, plus a higher-numbered sibling chapter
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(campaign=campaign)
        chapter = await campaign_chapter_factory(name="Chapter A", book=book, number=1)
        sibling = await campaign_chapter_factory(name="Chapter B", book=book, number=2)
        chapter_note = await note_factory(company=company, chapter=chapter)
        chapter_asset = await s3asset_factory(company=company, uploaded_by=user, chapter=chapter)

        # When the chapter is deleted
        service = CampaignService()
        await service.delete_chapter_and_renumber(chapter)

        await chapter.refresh_from_db()
        await chapter_note.refresh_from_db()
        await chapter_asset.refresh_from_db()
        await sibling.refresh_from_db()

        # Then the chapter, its note, and its asset are archived under one batch id
        assert chapter.is_archived
        assert chapter_note.is_archived
        assert chapter_asset.is_archived
        assert chapter.archive_batch_id is not None
        assert chapter_note.archive_batch_id == chapter.archive_batch_id
        assert chapter_asset.archive_batch_id == chapter.archive_batch_id

        # And the sibling chapter is renumbered down
        assert sibling.number == 1

    async def test_archive_campaign(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        campaign_chapter_factory: Callable[..., CampaignChapter],
    ) -> None:
        """Verify archive_campaign soft-archives campaign, books, and chapters."""
        # Given a campaign with books and chapters
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        book1 = await campaign_book_factory(campaign=campaign)
        book2 = await campaign_book_factory(campaign=campaign)
        chapter1 = await campaign_chapter_factory(book=book1)
        chapter2 = await campaign_chapter_factory(book=book1)

        # When the campaign is archived
        service = CampaignService()
        await service.archive_campaign(campaign)
        await campaign.refresh_from_db()
        await book1.refresh_from_db()
        await book2.refresh_from_db()
        await chapter1.refresh_from_db()
        await chapter2.refresh_from_db()

        # Then all should be archived
        assert campaign.is_archived
        assert book1.is_archived
        assert book2.is_archived
        assert chapter1.is_archived
        assert chapter2.is_archived

    async def test_archive_campaign_cascades_to_characters_and_notes(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        character_factory: Callable[..., Character],
        specialty_factory: Callable[..., Specialty],
        note_factory: Callable[..., Note],
        diceroll_factory: Callable[..., DiceRoll],
        user_factory: Callable[..., object],
    ) -> None:
        """Verify archive_campaign cascades to characters, their data, and notes under one batch."""
        # Given a campaign with a character, that character's specialty/note, and a campaign note
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        character = await character_factory(company=company, campaign=campaign)
        specialty = await specialty_factory(character=character)
        character_note = await note_factory(company=company, character=character)
        campaign_note = await note_factory(company=company, campaign=campaign)
        # And a dice roll on the campaign, which is a historical artifact that must survive
        user = await user_factory(company=company)
        dice_roll = await diceroll_factory(company=company, user=user, campaign=campaign)

        # When the campaign is archived
        service = CampaignService()
        await service.archive_campaign(campaign)

        # Then the campaign, character, specialty, and both notes are archived under one batch
        await campaign.refresh_from_db()
        await character.refresh_from_db()
        await specialty.refresh_from_db()
        await character_note.refresh_from_db()
        await campaign_note.refresh_from_db()
        await dice_roll.refresh_from_db()

        assert campaign.is_archived
        assert character.is_archived
        assert specialty.is_archived
        assert character_note.is_archived
        assert campaign_note.is_archived
        assert campaign.archive_batch_id is not None
        assert character.archive_batch_id == campaign.archive_batch_id
        assert specialty.archive_batch_id == campaign.archive_batch_id
        assert character_note.archive_batch_id == campaign.archive_batch_id
        assert campaign_note.archive_batch_id == campaign.archive_batch_id

        # And the dice roll survives
        assert dice_roll.is_archived is False

    async def test_validate_campaign_characters_returns_active_in_campaign(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        character_factory: Callable[..., Character],
    ) -> None:
        """Verify valid in-campaign character IDs are returned."""
        # Given a campaign with two active characters
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        char_a = await character_factory(company=company, campaign=campaign)
        char_b = await character_factory(company=company, campaign=campaign)

        # When validating those IDs
        result = await CampaignService().validate_campaign_characters(
            character_ids=[char_a.id, char_b.id], campaign_id=campaign.id
        )

        # Then both characters are returned
        assert {c.id for c in result} == {char_a.id, char_b.id}

    async def test_validate_campaign_characters_rejects_other_campaign(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        character_factory: Callable[..., Character],
    ) -> None:
        """Verify a character from another campaign is rejected."""
        # Given a character in a different campaign
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        other_campaign = await campaign_factory(company=company)
        foreign = await character_factory(company=company, campaign=other_campaign)

        # When validating it against the first campaign
        # Then a ValidationError is raised
        with pytest.raises(ValidationError):
            await CampaignService().validate_campaign_characters(
                character_ids=[foreign.id], campaign_id=campaign.id
            )

    async def test_validate_campaign_characters_rejects_archived(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        character_factory: Callable[..., Character],
    ) -> None:
        """Verify an archived character is rejected."""
        # Given an archived character in the campaign
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        archived = await character_factory(company=company, campaign=campaign, is_archived=True)

        # When validating it
        # Then a ValidationError is raised
        with pytest.raises(ValidationError):
            await CampaignService().validate_campaign_characters(
                character_ids=[archived.id], campaign_id=campaign.id
            )

    async def test_validate_campaign_characters_empty_returns_empty(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
    ) -> None:
        """Verify an empty ID list short-circuits to an empty result."""
        # Given a campaign
        company = await company_factory()
        campaign = await campaign_factory(company=company)

        # When validating an empty list
        result = await CampaignService().validate_campaign_characters(
            character_ids=[], campaign_id=campaign.id
        )

        # Then the result is empty
        assert result == []

    async def test_validate_campaign_characters_deduplicates_ids(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        character_factory: Callable[..., Character],
    ) -> None:
        """Verify duplicate IDs in the input are collapsed to a single result entry."""
        # Given a campaign with one character
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        char = await character_factory(company=company, campaign=campaign)

        # When the same ID is submitted twice
        result = await CampaignService().validate_campaign_characters(
            character_ids=[char.id, char.id], campaign_id=campaign.id
        )

        # Then exactly one character object is returned
        assert len(result) == 1
        assert result[0].id == char.id

    async def test_validate_campaign_characters_rejects_mixed_validity(
        self,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        character_factory: Callable[..., Character],
    ) -> None:
        """Verify one valid and one cross-campaign ID together are rejected."""
        # Given a valid in-campaign character and a character in another campaign
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        other_campaign = await campaign_factory(company=company)
        valid = await character_factory(company=company, campaign=campaign)
        foreign = await character_factory(company=company, campaign=other_campaign)

        # When validating the two together against the first campaign
        # Then a ValidationError is raised
        with pytest.raises(ValidationError):
            await CampaignService().validate_campaign_characters(
                character_ids=[valid.id, foreign.id], campaign_id=campaign.id
            )
