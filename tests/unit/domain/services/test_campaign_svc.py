"""Unit tests for campaign services."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.domain.services import CampaignService
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.models import Campaign, CampaignBook, CampaignChapter

pytestmark = pytest.mark.anyio


class TestCampaignService:
    """Test the campaign service."""

    async def test_get_next_book_number_first_book(
        self,
        campaign_factory: Callable[[], Campaign],
        debug: Callable[[...], None],
    ) -> None:
        """Test the get_next_book_number method."""
        campaign = await campaign_factory()

        # when the next book number is requested
        service = CampaignService()
        next_book_number = await service.get_next_book_number(campaign)

        # then the next book number should be 1
        assert next_book_number == 1

    async def test_get_next_book_number(
        self,
        campaign_factory: Callable[[], Campaign],
        campaign_book_factory: Callable[[], CampaignBook],
        debug: Callable[[...], None],
    ) -> None:
        """Test the get_next_book_number method."""
        campaign = await campaign_factory()
        await campaign_book_factory(campaign_id=campaign.id)
        await campaign_book_factory(campaign_id=campaign.id)
        await campaign_book_factory(campaign_id=campaign.id)

        # when the next book number is requested
        service = CampaignService()
        next_book_number = await service.get_next_book_number(campaign)

        # then the next book number should be 4
        assert next_book_number == 4

    async def test_get_next_chapter_number_first_chapter(
        self,
        campaign_book_factory: Callable[[], CampaignBook],
        debug: Callable[[...], None],
    ) -> None:
        """Test the get_next_chapter_number method."""
        book = await campaign_book_factory()

        # when the next chapter number is requested
        service = CampaignService()
        next_chapter_number = await service.get_next_chapter_number(book)

        # then the next chapter number should be 1
        assert next_chapter_number == 1

    async def test_get_next_chapter_number(
        self,
        campaign_book_factory: Callable[[], CampaignBook],
        campaign_chapter_factory: Callable[[], CampaignChapter],
        debug: Callable[[...], None],
    ) -> None:
        """Test the get_next_chapter_number method."""
        book = await campaign_book_factory()
        await campaign_chapter_factory(book_id=book.id)
        await campaign_chapter_factory(book_id=book.id)

        # when the next chapter number is requested
        service = CampaignService()
        next_chapter_number = await service.get_next_chapter_number(book)

        # then the next chapter number should be 3
        assert next_chapter_number == 3

    async def test_renumber_books(
        self,
        campaign_factory: Callable[[], Campaign],
        campaign_book_factory: Callable[[], CampaignBook],
        debug: Callable[[...], None],
    ) -> None:
        """Test the renumber_books method."""
        campaign = await campaign_factory()
        booka = await campaign_book_factory(name="Book A", campaign_id=campaign.id)
        bookb = await campaign_book_factory(name="Book B", campaign_id=campaign.id)
        bookc = await campaign_book_factory(name="Book C", campaign_id=campaign.id)
        bookd = await campaign_book_factory(name="Book D", campaign_id=campaign.id)

        # when the bookd is renumberd to 2
        service = CampaignService()
        await service.renumber_books(bookd, 2)
        await booka.sync()
        await bookb.sync()
        await bookc.sync()
        await bookd.sync()

        # then the books should be in the following order: 1, 3, 4, 2
        assert booka.number == 1
        assert bookb.number == 3
        assert bookc.number == 4
        assert bookd.number == 2

        # when the bookd is renumberd back to 4
        await service.renumber_books(bookd, 4)
        await booka.sync()
        await bookb.sync()
        await bookc.sync()
        await bookd.sync()

        # then the books should be in the following order: 1, 2, 3, 4
        assert booka.number == 1
        assert bookb.number == 2
        assert bookc.number == 3
        assert bookd.number == 4

    async def test_renumber_books_out_of_range(
        self,
        campaign_factory: Callable[[], Campaign],
        campaign_book_factory: Callable[[], CampaignBook],
        debug: Callable[[...], None],
    ) -> None:
        """Test the renumber_books method."""
        campaign = await campaign_factory()
        book = await campaign_book_factory(name="Book A", campaign_id=campaign.id)

        # when the book is renumberd to 2
        # then a ValidationError should be raised
        service = CampaignService()
        with pytest.raises(ValidationError):
            await service.renumber_books(book, 2)

    async def test_renumber_books_less_than_one(
        self,
        campaign_factory: Callable[[], Campaign],
        campaign_book_factory: Callable[[], CampaignBook],
        debug: Callable[[...], None],
    ) -> None:
        """Test the renumber_books method."""
        campaign = await campaign_factory()
        book = await campaign_book_factory(name="Book A", campaign_id=campaign.id)

        # when the book is renumberd to 0
        # then a ValidationError should be raised
        service = CampaignService()
        with pytest.raises(ValidationError):
            await service.renumber_books(book, 0)

    async def test_renumber_chapters(
        self,
        campaign_book_factory: Callable[[], CampaignBook],
        campaign_chapter_factory: Callable[[], CampaignChapter],
        debug: Callable[[...], None],
    ) -> None:
        """Test the renumber_chapters method."""
        book = await campaign_book_factory()
        chaptera = await campaign_chapter_factory(name="Chapter A", book_id=book.id)
        chapterb = await campaign_chapter_factory(name="Chapter B", book_id=book.id)
        chapterc = await campaign_chapter_factory(name="Chapter C", book_id=book.id)
        chapterd = await campaign_chapter_factory(name="Chapter D", book_id=book.id)

        # when the chapterd is renumberd to 2
        service = CampaignService()
        await service.renumber_chapters(chapterd, 2)
        await chaptera.sync()
        await chapterb.sync()
        await chapterc.sync()
        await chapterd.sync()

        # then the chapters should be in the following order: 1, 3, 4, 2
        assert chaptera.number == 1
        assert chapterb.number == 3
        assert chapterc.number == 4

        # when the chapterd is renumberd back to 4
        await service.renumber_chapters(chapterd, 4)
        await chaptera.sync()
        await chapterb.sync()
        await chapterc.sync()
        await chapterd.sync()

        # then the chapters should be in the following order: 1, 2, 3, 4
        assert chaptera.number == 1
        assert chapterb.number == 2
        assert chapterc.number == 3
        assert chapterd.number == 4

    async def test_renumber_chapters_out_of_range(
        self,
        campaign_book_factory: Callable[[], CampaignBook],
        campaign_chapter_factory: Callable[[], CampaignChapter],
        debug: Callable[[...], None],
    ) -> None:
        """Test the renumber_chapters method."""
        book = await campaign_book_factory()
        chapter = await campaign_chapter_factory(name="Chapter A", book_id=book.id)

        # when the chapter is renumberd to 2
        # then a ValidationError should be raised
        service = CampaignService()
        with pytest.raises(ValidationError):
            await service.renumber_chapters(chapter, 2)

    async def test_renumber_chapters_less_than_one(
        self,
        campaign_book_factory: Callable[[], CampaignBook],
        campaign_chapter_factory: Callable[[], CampaignChapter],
        debug: Callable[[...], None],
    ) -> None:
        """Test the renumber_chapters method."""
        book = await campaign_book_factory()
        chapter = await campaign_chapter_factory(name="Chapter A", book_id=book.id)

        # when the chapter is renumberd to 0
        # then a ValidationError should be raised
        service = CampaignService()
        with pytest.raises(ValidationError):
            await service.renumber_chapters(chapter, 0)

    async def test_delete_book_and_renumber_one_book(
        self,
        campaign_factory: Callable[[], Campaign],
        campaign_book_factory: Callable[[], CampaignBook],
        debug: Callable[[...], None],
    ) -> None:
        """Test the delete_book_and_renumber method."""
        campaign = await campaign_factory()
        book = await campaign_book_factory(name="Book A", campaign_id=campaign.id)

        # when the book is deleted
        service = CampaignService()

        await service.delete_book_and_renumber(book)
        await book.sync()

        # then the book should be deleted
        assert book.is_archived
        assert book.number == 1

    async def test_delete_book_and_renumber_multiple_books(
        self,
        campaign_factory: Callable[[], Campaign],
        campaign_book_factory: Callable[[], CampaignBook],
        debug: Callable[[...], None],
    ) -> None:
        """Test the delete_book_and_renumber method."""
        campaign = await campaign_factory()
        booka = await campaign_book_factory(name="Book A", campaign_id=campaign.id, number=1)
        bookb = await campaign_book_factory(name="Book B", campaign_id=campaign.id, number=2)
        bookc = await campaign_book_factory(name="Book C", campaign_id=campaign.id, number=3)
        bookd = await campaign_book_factory(name="Book D", campaign_id=campaign.id, number=4)

        # when the bookc is deleted
        service = CampaignService()
        await service.delete_book_and_renumber(bookb)
        await booka.sync()
        await bookb.sync()
        await bookc.sync()
        await bookd.sync()

        # then the books should be in the following order: 1, 2, 3
        assert booka.number == 1
        assert bookb.is_archived
        assert bookc.number == 2
        assert bookd.number == 3

    async def test_delete_chapter_and_renumber_one_chapter(
        self,
        campaign_book_factory: Callable[[], CampaignBook],
        campaign_chapter_factory: Callable[[], CampaignChapter],
        debug: Callable[[...], None],
    ) -> None:
        """Test the delete_chapter_and_renumber method."""
        book = await campaign_book_factory()
        chapter = await campaign_chapter_factory(name="Chapter A", book_id=book.id)

        # when the chapter is deleted
        service = CampaignService()
        await service.delete_chapter_and_renumber(chapter)
        await chapter.sync()

        # then the chapter should be deleted
        assert chapter.is_archived
        assert chapter.number == 1

    async def test_delete_chapter_and_renumber_multiple_chapters(
        self,
        campaign_book_factory: Callable[[], CampaignBook],
        campaign_chapter_factory: Callable[[], CampaignChapter],
        debug: Callable[[...], None],
    ) -> None:
        """Test the delete_chapter_and_renumber method."""
        book = await campaign_book_factory()
        chaptera = await campaign_chapter_factory(name="Chapter A", book_id=book.id, number=1)
        chapterb = await campaign_chapter_factory(name="Chapter B", book_id=book.id, number=2)
        chapterc = await campaign_chapter_factory(name="Chapter C", book_id=book.id, number=3)
        chapterd = await campaign_chapter_factory(name="Chapter D", book_id=book.id, number=4)

        # when the chapterc is deleted
        service = CampaignService()
        await service.delete_chapter_and_renumber(chapterb)

        await chaptera.sync()
        await chapterb.sync()
        await chapterc.sync()
        await chapterd.sync()

        # then the chapters should be in the following order: 1, 2, 3
        assert chaptera.number == 1
        assert chapterb.is_archived
        assert chapterc.number == 2
        assert chapterd.number == 3
