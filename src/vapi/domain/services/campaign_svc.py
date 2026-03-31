"""Campaign service."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from vapi.db.models import Campaign, CampaignBook, CampaignChapter
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from beanie import Document, PydanticObjectId


class CampaignService:
    """Manage ordered numbering of campaign books and chapters."""

    async def get_next_book_number(self, campaign: Campaign) -> int:
        """Get the next sequential book number for a campaign."""
        return await self._get_next_number(CampaignBook, CampaignBook.campaign_id, campaign.id)

    async def get_next_chapter_number(self, book: CampaignBook) -> int:
        """Get the next sequential chapter number for a book."""
        return await self._get_next_number(CampaignChapter, CampaignChapter.book_id, book.id)

    async def renumber_books(self, book: CampaignBook, new_number: int) -> CampaignBook:
        """Move a book to a new position, shifting surrounding books to maintain a contiguous sequence."""
        return await self._renumber_item(
            item=book,
            model=CampaignBook,
            parent_field=CampaignBook.campaign_id,
            parent_id=book.campaign_id,
            new_number=new_number,
            label="books in the campaign",
        )

    async def renumber_chapters(self, chapter: CampaignChapter, new_number: int) -> CampaignChapter:
        """Move a chapter to a new position, shifting surrounding chapters to maintain a contiguous sequence."""
        return await self._renumber_item(
            item=chapter,
            model=CampaignChapter,
            parent_field=CampaignChapter.book_id,
            parent_id=chapter.book_id,
            new_number=new_number,
            label="chapters in the book",
        )

    async def delete_book_and_renumber(self, book: CampaignBook) -> None:
        """Soft-delete a book and shift higher-numbered books down to fill the gap."""
        await self._archive_and_renumber(
            item=book,
            model=CampaignBook,
            parent_field=CampaignBook.campaign_id,
            parent_id=book.campaign_id,
        )

    async def delete_chapter_and_renumber(self, chapter: CampaignChapter) -> None:
        """Soft-delete a chapter and shift higher-numbered chapters down to fill the gap."""
        await self._archive_and_renumber(
            item=chapter,
            model=CampaignChapter,
            parent_field=CampaignChapter.book_id,
            parent_id=chapter.book_id,
        )

    @staticmethod
    async def _get_next_number(
        model: type[Document], parent_field: Any, parent_id: PydanticObjectId
    ) -> int:
        """Return count of active siblings + 1."""
        count = await model.find(
            parent_field == parent_id,
            model.is_archived == False,
        ).count()
        return count + 1

    @staticmethod
    async def _renumber_item(
        *,
        item: Document,
        model: type[Document],
        parent_field: Any,
        parent_id: PydanticObjectId,
        new_number: int,
        label: str,
    ) -> Document:
        """Move an item to a new position and shift siblings to maintain contiguous numbering."""
        siblings = await model.find(
            parent_field == parent_id,
            model.is_archived == False,
        ).to_list()

        if new_number > len(siblings):
            msg = f"New number {new_number} is greater than the number of {label} ({len(siblings)})"
            raise ValidationError(msg)
        if new_number < 1:
            msg = f"New number {new_number} is less than 1"
            raise ValidationError(msg)

        original_number = item.number
        item.number = new_number

        saves: list[Any] = []
        if new_number > original_number:
            for s in siblings:
                if original_number < s.number <= new_number:
                    s.number -= 1
                    saves.append(s.save())
        else:
            for s in siblings:
                if new_number <= s.number < original_number:
                    s.number += 1
                    saves.append(s.save())

        if saves:
            await asyncio.gather(*saves)

        await item.save()
        return item

    @staticmethod
    async def _archive_and_renumber(
        *,
        item: Document,
        model: type[Document],
        parent_field: Any,
        parent_id: PydanticObjectId,
    ) -> None:
        """Soft-delete an item and shift higher-numbered siblings down to fill the gap."""
        siblings = await model.find(
            parent_field == parent_id,
            model.is_archived == False,
        ).to_list()

        saves: list[Any] = []
        for s in siblings:
            if s.number > item.number:
                s.number -= 1
                saves.append(s.save())

        item.is_archived = True
        saves.append(item.save())
        await asyncio.gather(*saves)
