"""Campaign service."""

import asyncio
from typing import Protocol
from uuid import UUID

from tortoise.expressions import F
from tortoise.models import Model

from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.lib.exceptions import ValidationError
from vapi.utils.time import time_now


class _NumberedItem(Protocol):
    """Protocol for campaign items that have a numeric position field."""

    id: UUID
    number: int


class CampaignService:
    """Manage ordered numbering of campaign books and chapters."""

    async def get_next_book_number(self, campaign: Campaign) -> int:
        """Get the next sequential book number for a campaign."""
        return await self._get_next_number(CampaignBook, "campaign_id", campaign.id)

    async def get_next_chapter_number(self, book: CampaignBook) -> int:
        """Get the next sequential chapter number for a book."""
        return await self._get_next_number(CampaignChapter, "book_id", book.id)

    async def renumber_books(self, book: CampaignBook, new_number: int) -> CampaignBook:
        """Move a book to a new position, shifting surrounding books to maintain a contiguous sequence."""
        await self._renumber_item(
            item=book,
            model=CampaignBook,
            parent_field="campaign_id",
            parent_id=book.campaign_id,  # type: ignore[attr-defined]
            new_number=new_number,
            label="books in the campaign",
        )
        book.number = new_number
        return book

    async def renumber_chapters(self, chapter: CampaignChapter, new_number: int) -> CampaignChapter:
        """Move a chapter to a new position, shifting surrounding chapters to maintain a contiguous sequence."""
        await self._renumber_item(
            item=chapter,
            model=CampaignChapter,
            parent_field="book_id",
            parent_id=chapter.book_id,  # type: ignore[attr-defined]
            new_number=new_number,
            label="chapters in the book",
        )
        chapter.number = new_number
        return chapter

    async def delete_book_and_renumber(self, book: CampaignBook) -> None:
        """Soft-delete a book and shift higher-numbered books down to fill the gap."""
        await self._archive_and_renumber(
            item=book,
            model=CampaignBook,
            parent_field="campaign_id",
            parent_id=book.campaign_id,  # type: ignore[attr-defined]
        )

    async def delete_chapter_and_renumber(self, chapter: CampaignChapter) -> None:
        """Soft-delete a chapter and shift higher-numbered chapters down to fill the gap."""
        await self._archive_and_renumber(
            item=chapter,
            model=CampaignChapter,
            parent_field="book_id",
            parent_id=chapter.book_id,  # type: ignore[attr-defined]
        )

    async def archive_campaign(self, campaign: Campaign) -> None:
        """Soft-archive a campaign and all its books and chapters."""
        now = time_now()
        # Collect book IDs first to avoid a cross-table JOIN in the UPDATE, which
        # PostgreSQL disallows when the target table also appears in the FROM clause.
        book_ids = await CampaignBook.filter(campaign_id=campaign.id).values_list("id", flat=True)
        if book_ids:
            await CampaignChapter.filter(book_id__in=book_ids, is_archived=False).update(
                is_archived=True, archive_date=now
            )
        await CampaignBook.filter(campaign_id=campaign.id, is_archived=False).update(
            is_archived=True, archive_date=now
        )
        await Campaign.filter(id=campaign.id).update(is_archived=True, archive_date=now)

    @staticmethod
    async def _get_next_number(model: type[Model], parent_field: str, parent_id: UUID) -> int:
        """Derive the next position from count rather than MAX to avoid gaps from archived items."""
        count = await model.filter(**{parent_field: parent_id}, is_archived=False).count()
        return count + 1

    @staticmethod
    async def _renumber_item(
        *,
        item: _NumberedItem,
        model: type[Model],
        parent_field: str,
        parent_id: UUID,
        new_number: int,
        label: str,
    ) -> None:
        """Move an item to a new position and shift siblings to maintain contiguous numbering."""
        original_number = item.number
        if new_number == original_number:
            return

        sibling_count = await model.filter(**{parent_field: parent_id}, is_archived=False).count()

        if new_number > sibling_count:
            msg = f"New number {new_number} is greater than the number of {label} ({sibling_count})"
            raise ValidationError(msg)
        if new_number < 1:
            msg = f"New number {new_number} is less than 1"
            raise ValidationError(msg)

        if new_number > original_number:
            # Moving forward: shift items in (old, new] down by 1
            await (
                model.filter(
                    **{parent_field: parent_id},
                    number__gt=original_number,
                    number__lte=new_number,
                    is_archived=False,
                )
                .exclude(id=item.id)
                .update(number=F("number") - 1)
            )
        elif new_number < original_number:
            # Moving backward: shift items in [new, old) up by 1
            await (
                model.filter(
                    **{parent_field: parent_id},
                    number__gte=new_number,
                    number__lt=original_number,
                    is_archived=False,
                )
                .exclude(id=item.id)
                .update(number=F("number") + 1)
            )

        await model.filter(id=item.id).update(number=new_number)

    @staticmethod
    async def _archive_and_renumber(
        *,
        item: _NumberedItem,
        model: type[Model],
        parent_field: str,
        parent_id: UUID,
    ) -> None:
        """Soft-delete an item and shift higher-numbered siblings down to fill the gap."""
        await asyncio.gather(
            model.filter(
                **{parent_field: parent_id},
                number__gt=item.number,
                is_archived=False,
            ).update(number=F("number") - 1),
            model.filter(id=item.id).update(is_archived=True),
        )
