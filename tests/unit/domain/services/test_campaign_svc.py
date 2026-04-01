"""Unit tests for campaign services."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.domain.services import CampaignService
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
    from vapi.db.sql_models.company import Company

pytestmark = pytest.mark.anyio


class TestCampaignService:
    """Test the campaign service."""

    async def test_get_next_book_number_first_book(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
    ) -> None:
        """Verify get_next_book_number returns 1 for a campaign with no books."""
        # Given a campaign with no books
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)

        # When the next book number is requested
        service = CampaignService()
        next_book_number = await service.get_next_book_number(campaign)

        # Then the next book number should be 1
        assert next_book_number == 1

    async def test_get_next_book_number(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_campaign_book_factory: Callable[..., CampaignBook],
    ) -> None:
        """Verify get_next_book_number returns count + 1."""
        # Given a campaign with 3 books
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        await pg_campaign_book_factory(campaign=campaign)
        await pg_campaign_book_factory(campaign=campaign)
        await pg_campaign_book_factory(campaign=campaign)

        # When the next book number is requested
        service = CampaignService()
        next_book_number = await service.get_next_book_number(campaign)

        # Then the next book number should be 4
        assert next_book_number == 4

    async def test_get_next_chapter_number_first_chapter(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_campaign_book_factory: Callable[..., CampaignBook],
    ) -> None:
        """Verify get_next_chapter_number returns 1 for a book with no chapters."""
        # Given a book with no chapters
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        book = await pg_campaign_book_factory(campaign=campaign)

        # When the next chapter number is requested
        service = CampaignService()
        next_chapter_number = await service.get_next_chapter_number(book)

        # Then the next chapter number should be 1
        assert next_chapter_number == 1

    async def test_get_next_chapter_number(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_campaign_book_factory: Callable[..., CampaignBook],
        pg_campaign_chapter_factory: Callable[..., CampaignChapter],
    ) -> None:
        """Verify get_next_chapter_number returns count + 1."""
        # Given a book with 2 chapters
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        book = await pg_campaign_book_factory(campaign=campaign)
        await pg_campaign_chapter_factory(book=book)
        await pg_campaign_chapter_factory(book=book)

        # When the next chapter number is requested
        service = CampaignService()
        next_chapter_number = await service.get_next_chapter_number(book)

        # Then the next chapter number should be 3
        assert next_chapter_number == 3

    async def test_renumber_books(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_campaign_book_factory: Callable[..., CampaignBook],
    ) -> None:
        """Verify renumber_books shifts siblings correctly in both directions."""
        # Given a campaign with 4 books
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        booka = await pg_campaign_book_factory(name="Book A", campaign=campaign)
        bookb = await pg_campaign_book_factory(name="Book B", campaign=campaign)
        bookc = await pg_campaign_book_factory(name="Book C", campaign=campaign)
        bookd = await pg_campaign_book_factory(name="Book D", campaign=campaign)

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

    async def test_renumber_books_out_of_range(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_campaign_book_factory: Callable[..., CampaignBook],
    ) -> None:
        """Verify renumber_books raises ValidationError when number exceeds count."""
        # Given a campaign with 1 book
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        book = await pg_campaign_book_factory(name="Book A", campaign=campaign)

        # When the book is renumbered to 2
        # Then a ValidationError should be raised
        service = CampaignService()
        with pytest.raises(ValidationError):
            await service.renumber_books(book, 2)

    async def test_renumber_books_less_than_one(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_campaign_book_factory: Callable[..., CampaignBook],
    ) -> None:
        """Verify renumber_books raises ValidationError when number is less than 1."""
        # Given a campaign with 1 book
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        book = await pg_campaign_book_factory(name="Book A", campaign=campaign)

        # When the book is renumbered to 0
        # Then a ValidationError should be raised
        service = CampaignService()
        with pytest.raises(ValidationError):
            await service.renumber_books(book, 0)

    async def test_renumber_chapters(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_campaign_book_factory: Callable[..., CampaignBook],
        pg_campaign_chapter_factory: Callable[..., CampaignChapter],
    ) -> None:
        """Verify renumber_chapters shifts siblings correctly in both directions."""
        # Given a book with 4 chapters
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        book = await pg_campaign_book_factory(campaign=campaign)
        chaptera = await pg_campaign_chapter_factory(name="Chapter A", book=book)
        chapterb = await pg_campaign_chapter_factory(name="Chapter B", book=book)
        chapterc = await pg_campaign_chapter_factory(name="Chapter C", book=book)
        chapterd = await pg_campaign_chapter_factory(name="Chapter D", book=book)

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

    async def test_renumber_chapters_out_of_range(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_campaign_book_factory: Callable[..., CampaignBook],
        pg_campaign_chapter_factory: Callable[..., CampaignChapter],
    ) -> None:
        """Verify renumber_chapters raises ValidationError when number exceeds count."""
        # Given a book with 1 chapter
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        book = await pg_campaign_book_factory(campaign=campaign)
        chapter = await pg_campaign_chapter_factory(name="Chapter A", book=book)

        # When the chapter is renumbered to 2
        # Then a ValidationError should be raised
        service = CampaignService()
        with pytest.raises(ValidationError):
            await service.renumber_chapters(chapter, 2)

    async def test_renumber_chapters_less_than_one(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_campaign_book_factory: Callable[..., CampaignBook],
        pg_campaign_chapter_factory: Callable[..., CampaignChapter],
    ) -> None:
        """Verify renumber_chapters raises ValidationError when number is less than 1."""
        # Given a book with 1 chapter
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        book = await pg_campaign_book_factory(campaign=campaign)
        chapter = await pg_campaign_chapter_factory(name="Chapter A", book=book)

        # When the chapter is renumbered to 0
        # Then a ValidationError should be raised
        service = CampaignService()
        with pytest.raises(ValidationError):
            await service.renumber_chapters(chapter, 0)

    async def test_delete_book_and_renumber_one_book(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_campaign_book_factory: Callable[..., CampaignBook],
    ) -> None:
        """Verify delete_book_and_renumber soft-deletes a single book."""
        # Given a campaign with 1 book
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        book = await pg_campaign_book_factory(name="Book A", campaign=campaign)

        # When the book is deleted
        service = CampaignService()
        await service.delete_book_and_renumber(book)
        await book.refresh_from_db()

        # Then the book should be archived
        assert book.is_archived
        assert book.number == 1

    async def test_delete_book_and_renumber_multiple_books(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_campaign_book_factory: Callable[..., CampaignBook],
    ) -> None:
        """Verify delete_book_and_renumber shifts higher-numbered books down."""
        # Given a campaign with 4 books
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        booka = await pg_campaign_book_factory(name="Book A", campaign=campaign, number=1)
        bookb = await pg_campaign_book_factory(name="Book B", campaign=campaign, number=2)
        bookc = await pg_campaign_book_factory(name="Book C", campaign=campaign, number=3)
        bookd = await pg_campaign_book_factory(name="Book D", campaign=campaign, number=4)

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
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_campaign_book_factory: Callable[..., CampaignBook],
        pg_campaign_chapter_factory: Callable[..., CampaignChapter],
    ) -> None:
        """Verify delete_chapter_and_renumber soft-deletes a single chapter."""
        # Given a book with 1 chapter
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        book = await pg_campaign_book_factory(campaign=campaign)
        chapter = await pg_campaign_chapter_factory(name="Chapter A", book=book)

        # When the chapter is deleted
        service = CampaignService()
        await service.delete_chapter_and_renumber(chapter)
        await chapter.refresh_from_db()

        # Then the chapter should be archived
        assert chapter.is_archived
        assert chapter.number == 1

    async def test_delete_chapter_and_renumber_multiple_chapters(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_campaign_book_factory: Callable[..., CampaignBook],
        pg_campaign_chapter_factory: Callable[..., CampaignChapter],
    ) -> None:
        """Verify delete_chapter_and_renumber shifts higher-numbered chapters down."""
        # Given a book with 4 chapters
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        book = await pg_campaign_book_factory(campaign=campaign)
        chaptera = await pg_campaign_chapter_factory(name="Chapter A", book=book, number=1)
        chapterb = await pg_campaign_chapter_factory(name="Chapter B", book=book, number=2)
        chapterc = await pg_campaign_chapter_factory(name="Chapter C", book=book, number=3)
        chapterd = await pg_campaign_chapter_factory(name="Chapter D", book=book, number=4)

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

    async def test_archive_campaign(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_campaign_book_factory: Callable[..., CampaignBook],
        pg_campaign_chapter_factory: Callable[..., CampaignChapter],
    ) -> None:
        """Verify archive_campaign soft-archives campaign, books, and chapters."""
        # Given a campaign with books and chapters
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        book1 = await pg_campaign_book_factory(campaign=campaign)
        book2 = await pg_campaign_book_factory(campaign=campaign)
        chapter1 = await pg_campaign_chapter_factory(book=book1)
        chapter2 = await pg_campaign_chapter_factory(book=book1)

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
