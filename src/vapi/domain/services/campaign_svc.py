"""Campaign service."""

from __future__ import annotations

from vapi.constants import MAX_DANGER, MAX_DESPERATION
from vapi.db.models import Campaign, CampaignBook, CampaignChapter
from vapi.lib.exceptions import ValidationError


class CampaignService:
    """Campaign service."""

    def validate_desperation_level(self, desperation_level: int) -> int:
        """Validate the desperation level."""
        if desperation_level < 0 or desperation_level > MAX_DESPERATION:
            msg = f"Desperation level must be between 0 and {MAX_DESPERATION}"
            raise ValidationError(detail=msg)
        return desperation_level

    def validate_danger_level(self, danger_level: int) -> int:
        """Validate the danger level."""
        if danger_level < 0 or danger_level > MAX_DANGER:
            msg = f"Danger level must be between 0 and {MAX_DANGER}"
            raise ValidationError(detail=msg)
        return danger_level

    async def get_next_book_number(self, campaign: Campaign) -> int:
        """Get the next book number for a campaign."""
        campaign_books = await CampaignBook.find(
            CampaignBook.campaign_id == campaign.id,
            CampaignBook.is_archived == False,
        ).to_list()
        return len(campaign_books) + 1

    async def get_next_chapter_number(self, book: CampaignBook) -> int:
        """Get the next chapter number for a book."""
        campaign_chapters = await CampaignChapter.find(
            CampaignChapter.book_id == book.id,
            CampaignChapter.is_archived == False,
        ).to_list()
        return len(campaign_chapters) + 1

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
            for b in all_campaign_books:
                if original_number < b.number <= new_number:
                    b.number -= 1
                    await b.save()

        else:
            # Shift books up if the new number is lower
            for b in all_campaign_books:
                if new_number <= b.number < original_number:
                    b.number += 1
                    await b.save()

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
            for c in all_book_chapters:
                if original_number < c.number <= new_number:
                    c.number -= 1
                    await c.save()

        else:
            # Shift chapters up if the new number is lower
            for c in all_book_chapters:
                if new_number <= c.number < original_number:
                    c.number += 1
                    await c.save()

        await chapter.save()
        return chapter

    async def delete_book_and_renumber(self, book: CampaignBook) -> None:
        """Renumber the books for a campaign after a book is deleted."""
        all_campaign_books = await CampaignBook.find(
            CampaignBook.campaign_id == book.campaign_id,
            CampaignBook.is_archived == False,
        ).to_list()
        for b in all_campaign_books:
            if b.number > book.number:
                b.number -= 1
                await b.save()

        book.is_archived = True
        await book.save()

    async def delete_chapter_and_renumber(self, chapter: CampaignChapter) -> None:
        """Renumber the chapters for a book after a chapter is deleted."""
        all_book_chapters = await CampaignChapter.find(
            CampaignChapter.book_id == chapter.book_id,
            CampaignChapter.is_archived == False,
        ).to_list()
        for c in all_book_chapters:
            if c.number > chapter.number:
                c.number -= 1
                await c.save()

        chapter.is_archived = True
        await chapter.save()
