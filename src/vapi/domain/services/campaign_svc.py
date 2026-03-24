"""Campaign service."""

from __future__ import annotations

import asyncio

from vapi.db.models import Campaign, CampaignBook, CampaignChapter
from vapi.lib.exceptions import ValidationError


class CampaignService:
    """Campaign service."""

    async def get_next_book_number(self, campaign: Campaign) -> int:
        """Get the next book number for a campaign."""
        count = await CampaignBook.find(
            CampaignBook.campaign_id == campaign.id,
            CampaignBook.is_archived == False,
        ).count()
        return count + 1

    async def get_next_chapter_number(self, book: CampaignBook) -> int:
        """Get the next chapter number for a book."""
        count = await CampaignChapter.find(
            CampaignChapter.book_id == book.id,
            CampaignChapter.is_archived == False,
        ).count()
        return count + 1

    async def renumber_books(self, book: CampaignBook, new_number: int) -> CampaignBook:
        """Renumber the books for a campaign."""
        all_campaign_books = await CampaignBook.find(
            CampaignBook.campaign_id == book.campaign_id,
            CampaignBook.is_archived == False,
        ).to_list()

        if new_number > len(all_campaign_books):
            message = f"New number {new_number} is greater than the number of books in the campaign ({len(all_campaign_books) + 1})"
            raise ValidationError(message)
        if new_number < 1:
            message = f"New number {new_number} is less than 1"
            raise ValidationError(message)

        original_number = book.number
        book.number = new_number

        if new_number > original_number:
            # Shift books down if the new number is higher
            saves = []
            for b in all_campaign_books:
                if original_number < b.number <= new_number:
                    b.number -= 1
                    saves.append(b.save())
            if saves:
                await asyncio.gather(*saves)
        else:
            # Shift books up if the new number is lower
            saves = []
            for b in all_campaign_books:
                if new_number <= b.number < original_number:
                    b.number += 1
                    saves.append(b.save())
            if saves:
                await asyncio.gather(*saves)

        await book.save()
        return book

    async def renumber_chapters(self, chapter: CampaignChapter, new_number: int) -> CampaignChapter:
        """Renumber the chapters for a book."""
        all_book_chapters = await CampaignChapter.find(
            CampaignChapter.book_id == chapter.book_id,
            CampaignChapter.is_archived == False,
        ).to_list()

        if new_number > len(all_book_chapters):
            message = f"New number {new_number} is greater than the number of chapters in the book ({len(all_book_chapters) + 1})"
            raise ValidationError(message)
        if new_number < 1:
            message = f"New number {new_number} is less than 1"
            raise ValidationError(message)

        original_number = chapter.number
        chapter.number = new_number

        if new_number > original_number:
            # Shift chapters down if the new number is higher
            saves = []
            for c in all_book_chapters:
                if original_number < c.number <= new_number:
                    c.number -= 1
                    saves.append(c.save())
            if saves:
                await asyncio.gather(*saves)
        else:
            # Shift chapters up if the new number is lower
            saves = []
            for c in all_book_chapters:
                if new_number <= c.number < original_number:
                    c.number += 1
                    saves.append(c.save())
            if saves:
                await asyncio.gather(*saves)

        await chapter.save()
        return chapter

    async def delete_book_and_renumber(self, book: CampaignBook) -> None:
        """Renumber the books for a campaign after a book is deleted."""
        all_campaign_books = await CampaignBook.find(
            CampaignBook.campaign_id == book.campaign_id,
            CampaignBook.is_archived == False,
        ).to_list()
        saves = []
        for b in all_campaign_books:
            if b.number > book.number:
                b.number -= 1
                saves.append(b.save())
        if saves:
            await asyncio.gather(*saves)

        book.is_archived = True
        await book.save()

    async def delete_chapter_and_renumber(self, chapter: CampaignChapter) -> None:
        """Renumber the chapters for a book after a chapter is deleted."""
        all_book_chapters = await CampaignChapter.find(
            CampaignChapter.book_id == chapter.book_id,
            CampaignChapter.is_archived == False,
        ).to_list()
        saves = []
        for c in all_book_chapters:
            if c.number > chapter.number:
                c.number -= 1
                saves.append(c.save())
        if saves:
            await asyncio.gather(*saves)

        chapter.is_archived = True
        await chapter.save()
