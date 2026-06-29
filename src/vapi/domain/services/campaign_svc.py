"""Campaign service."""

from typing import Protocol
from uuid import UUID

from tortoise.expressions import F, Q
from tortoise.functions import Count
from tortoise.models import Model
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from vapi.constants import CharacterType
from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.character import Character
from vapi.lib.exceptions import ValidationError


def annotate_campaign_counts(qs: QuerySet[Campaign]) -> QuerySet[Campaign]:
    """Annotate a Campaign queryset with active child-resource counts for responses."""
    return qs.annotate(
        num_books=Count("books", _filter=Q(books__is_archived=False), distinct=True),
        num_chapters=Count(
            "books__chapters",
            _filter=Q(books__is_archived=False, books__chapters__is_archived=False),
            distinct=True,
        ),
        num_notes=Count("notes", _filter=Q(notes__is_archived=False), distinct=True),
        num_player_characters=Count(
            "characters",
            _filter=Q(characters__is_archived=False, characters__type=CharacterType.PLAYER),
            distinct=True,
        ),
        num_storyteller_characters=Count(
            "characters",
            _filter=Q(characters__is_archived=False, characters__type=CharacterType.STORYTELLER),
            distinct=True,
        ),
        num_npc_characters=Count(
            "characters",
            _filter=Q(characters__is_archived=False, characters__type=CharacterType.NPC),
            distinct=True,
        ),
    )


def annotate_book_counts(qs: QuerySet[CampaignBook]) -> QuerySet[CampaignBook]:
    """Annotate a CampaignBook queryset with active child-resource counts for responses."""
    return qs.annotate(
        num_chapters=Count("chapters", _filter=Q(chapters__is_archived=False), distinct=True),
        num_notes=Count("notes", _filter=Q(notes__is_archived=False), distinct=True),
        num_assets=Count("assets", _filter=Q(assets__is_archived=False), distinct=True),
    )


def annotate_chapter_counts(qs: QuerySet[CampaignChapter]) -> QuerySet[CampaignChapter]:
    """Annotate a CampaignChapter queryset with active child-resource counts for responses."""
    return qs.annotate(
        num_notes=Count("notes", _filter=Q(notes__is_archived=False), distinct=True),
        num_assets=Count("assets", _filter=Q(assets__is_archived=False), distinct=True),
    )


class _NumberedItem(Protocol):
    """Protocol for campaign items that have a numeric position field."""

    id: UUID
    number: int


class CampaignService:
    """Manage campaign structure: book/chapter ordering and character validation for assignments."""

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
            parent_id=book.campaign_id,  # ty:ignore[unresolved-attribute]
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
            parent_id=chapter.book_id,  # ty:ignore[unresolved-attribute]
            new_number=new_number,
            label="chapters in the book",
        )
        chapter.number = new_number
        return chapter

    @staticmethod
    async def _renumber_after_delete(
        *, model: type[Model], parent_field: str, parent_id: UUID, number: int
    ) -> None:
        """Shift siblings numbered above ``number`` down by one to fill a deleted item's slot."""
        await model.filter(
            **{parent_field: parent_id}, number__gt=number, is_archived=False
        ).update(number=F("number") - 1)

    async def delete_book_and_renumber(self, book: CampaignBook) -> None:
        """Soft-delete a book (cascading to its chapters, notes, and assets) and renumber siblings."""
        # Local import: campaign_svc is imported before character_trait_svc in
        # services/__init__, so a top-level handlers import would cycle.
        from vapi.domain.handlers import archive_book

        async with in_transaction():
            await self._renumber_after_delete(
                model=CampaignBook,
                parent_field="campaign_id",
                parent_id=book.campaign_id,  # ty:ignore[unresolved-attribute]
                number=book.number,
            )
            await archive_book(book=book)

    async def delete_chapter_and_renumber(self, chapter: CampaignChapter) -> None:
        """Soft-delete a chapter (cascading to its notes and assets) and renumber siblings."""
        # Local import: campaign_svc is imported before character_trait_svc in
        # services/__init__, so a top-level handlers import would cycle.
        from vapi.domain.handlers import archive_chapter

        async with in_transaction():
            await self._renumber_after_delete(
                model=CampaignChapter,
                parent_field="book_id",
                parent_id=chapter.book_id,  # ty:ignore[unresolved-attribute]
                number=chapter.number,
            )
            await archive_chapter(chapter=chapter)

    async def archive_campaign(self, campaign: Campaign) -> None:
        """Soft-archive a campaign and cascade to its books, chapters, characters, and data."""
        from vapi.domain.handlers import archive_campaign

        await archive_campaign(campaign=campaign)

    async def validate_campaign_characters(
        self, *, character_ids: list[UUID], campaign_id: UUID
    ) -> list[Character]:
        """Resolve character IDs for chapter M2M assignment, enforcing campaign scope.

        Use when accepting a caller-supplied ``character_ids`` list on chapter create or
        patch: every ID must reference an active character in the chapter's own campaign,
        preventing cross-campaign links and the assignment of archived characters.

        Args:
            character_ids: Caller-supplied character UUIDs (may contain duplicates).
            campaign_id: The campaign the chapter belongs to.

        Returns:
            The validated Character objects.

        Raises:
            ValidationError: If any ID is unknown, archived, or in another campaign.
        """
        if not character_ids:
            return []

        # dict.fromkeys dedupes while preserving caller order for the error message
        unique_ids = list(dict.fromkeys(character_ids))
        characters = await Character.filter(
            id__in=unique_ids, campaign_id=campaign_id, is_archived=False
        )
        found = {c.id for c in characters}
        invalid = [str(cid) for cid in unique_ids if cid not in found]
        if invalid:
            raise ValidationError(
                detail="One or more character IDs are not valid for this campaign",
                invalid_parameters=[
                    {
                        "field": "character_ids",
                        "message": f"Characters not found in this campaign or archived: {', '.join(invalid)}",
                    },
                ],
            )
        return characters

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
