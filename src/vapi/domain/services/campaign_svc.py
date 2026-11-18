"""Campaign service."""

from dataclasses import dataclass
from uuid import UUID

from tortoise.expressions import F, Q
from tortoise.functions import Count
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from vapi.constants import CharacterType
from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.character import Character
from vapi.lib.exceptions import NotFoundError, ValidationError
from vapi.lib.guards import visible_characters


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


type _NumberedItem = CampaignBook | CampaignChapter


@dataclass(frozen=True)
class _Numbering:
    """Where one kind of numbered item sits: its model, its parent, and its labels."""

    model: type[CampaignBook] | type[CampaignChapter]
    parent_model: type[Campaign] | type[CampaignBook]
    parent_field: str
    parent_label: str
    label: str
    plural: str

    def parent_id(self, item: _NumberedItem) -> UUID:
        """Return the id of the parent the item is numbered within."""
        return getattr(item, self.parent_field)


_BOOKS = _Numbering(
    model=CampaignBook,
    parent_model=Campaign,
    parent_field="campaign_id",
    parent_label="Campaign",
    label="Book",
    plural="books in the campaign",
)
_CHAPTERS = _Numbering(
    model=CampaignChapter,
    parent_model=CampaignBook,
    parent_field="book_id",
    parent_label="Book",
    label="Chapter",
    plural="chapters in the book",
)


class CampaignService:
    """Manage campaign structure: book/chapter ordering and character validation for assignments."""

    async def get_next_book_number(self, campaign: Campaign) -> int:
        """Lock the campaign and get its next book number. Call inside the book's create transaction.

        Raises:
            NotFoundError: If the campaign was archived after it was loaded.
        """
        return await self._get_next_number(_BOOKS, campaign.id)

    async def get_next_chapter_number(self, book: CampaignBook) -> int:
        """Lock the book and get its next chapter number. Call inside the chapter's create transaction.

        Raises:
            NotFoundError: If the book was archived after it was loaded.
        """
        return await self._get_next_number(_CHAPTERS, book.id)

    async def renumber_books(self, book: CampaignBook, new_number: int) -> int:
        """Move a book to a new position, shifting surrounding books to maintain a contiguous sequence.

        Returns:
            The book's number before the move, read under lock for the audit log.
        """
        return await self._renumber(item=book, numbering=_BOOKS, new_number=new_number)

    async def renumber_chapters(self, chapter: CampaignChapter, new_number: int) -> int:
        """Move a chapter to a new position, shifting surrounding chapters to maintain a contiguous sequence.

        Returns:
            The chapter's number before the move, read under lock for the audit log.
        """
        return await self._renumber(item=chapter, numbering=_CHAPTERS, new_number=new_number)

    async def delete_book_and_renumber(self, book: CampaignBook) -> None:
        """Soft-delete a book (cascading to its chapters, notes, and assets) and renumber siblings."""
        # Local import: campaign_svc is imported before character_trait_svc in
        # services/__init__, so a top-level handlers import would cycle.
        from vapi.domain.handlers import archive_book

        async with in_transaction():
            await self._delete_and_renumber(item=book, numbering=_BOOKS)
            await archive_book(book=book)

    async def delete_chapter_and_renumber(self, chapter: CampaignChapter) -> None:
        """Soft-delete a chapter (cascading to its notes and assets) and renumber siblings."""
        from vapi.domain.handlers import archive_chapter

        async with in_transaction():
            await self._delete_and_renumber(item=chapter, numbering=_CHAPTERS)
            await archive_chapter(chapter=chapter)

    async def archive_campaign(self, campaign: Campaign) -> None:
        """Soft-archive a campaign and cascade to its books, chapters, characters, and data."""
        from vapi.domain.handlers import archive_campaign

        await archive_campaign(campaign=campaign)

    async def validate_campaign_characters(
        self, *, character_ids: list[UUID], campaign_id: UUID, include_storyteller: bool
    ) -> list[Character]:
        """Resolve character IDs for chapter M2M assignment, enforcing campaign scope.

        Use when accepting a caller-supplied ``character_ids`` list on chapter create or
        patch: every ID must reference an active character in the chapter's own campaign,
        preventing cross-campaign links and the assignment of archived characters.

        Args:
            character_ids: Caller-supplied character UUIDs (may contain duplicates).
            campaign_id: The campaign the chapter belongs to.
            include_storyteller: Whether the caller may link STORYTELLER-type characters,
                which only storytellers and admins may see.

        Returns:
            The validated Character objects.

        Raises:
            ValidationError: If any ID is unknown, archived, in another campaign, or a
                STORYTELLER character the caller may not see.
        """
        if not character_ids:
            return []

        # dict.fromkeys dedupes while preserving caller order for the error message
        unique_ids = list(dict.fromkeys(character_ids))
        characters = await visible_characters(
            Character.filter(id__in=unique_ids, campaign_id=campaign_id, is_archived=False),
            include_storyteller=include_storyteller,
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

    async def replace_chapter_characters(
        self,
        *,
        chapter: CampaignChapter,
        characters: list[Character],
        include_storyteller: bool,
    ) -> list[Character]:
        """Replace the chapter's character links that the caller can see with ``characters``.

        Leave STORYTELLER-type links in place for a caller without storyteller visibility,
        so resubmitting the list it was shown never removes links it was never shown.

        Args:
            chapter: The chapter whose links to replace.
            characters: The validated characters to link.
            include_storyteller: Whether the caller may see STORYTELLER-type characters.

        Returns:
            The previously linked characters the caller could see, archived ones included.
        """
        new_ids = {c.id for c in characters}
        async with in_transaction():
            previous = await visible_characters(
                chapter.characters.all(), include_storyteller=include_storyteller
            )
            previous_ids = {c.id for c in previous}
            stale = [c for c in previous if c.id not in new_ids]
            added = [c for c in characters if c.id not in previous_ids]
            if stale:
                await chapter.characters.remove(*stale)
            if added:
                await chapter.characters.add(*added)
        return previous

    @staticmethod
    async def _lock_parent(*, numbering: _Numbering, parent_id: UUID) -> None:
        """Lock the active parent that numbers its children. Call inside a transaction.

        Raises:
            NotFoundError: If the parent is archived or gone.
        """
        if not await numbering.parent_model.lock_rows([parent_id], is_archived=False):
            raise NotFoundError(detail=f"{numbering.parent_label} not found")

    async def _get_next_number(self, numbering: _Numbering, parent_id: UUID) -> int:
        """Derive the next position from count rather than MAX to avoid gaps from archived items.

        The parent lock keeps a concurrent create, move, or delete from changing the count
        before the new item is saved.
        """
        await self._lock_parent(numbering=numbering, parent_id=parent_id)
        count = await numbering.model.filter(
            **{numbering.parent_field: parent_id}, is_archived=False
        ).count()
        return count + 1

    @staticmethod
    async def _lock_numbered_item(*, item: _NumberedItem, numbering: _Numbering) -> None:
        """Lock an item's parent, then the item, and reload the item. Call inside a transaction.

        Every number change in one parent takes the parent lock first, so concurrent moves
        and deletes run one at a time against committed numbers instead of shifting
        siblings from stale positions. Parent-then-child is the order an archive cascade
        takes, so the two cannot deadlock.

        Raises:
            NotFoundError: If the parent or the item is archived or gone.
        """
        await CampaignService._lock_parent(numbering=numbering, parent_id=numbering.parent_id(item))
        if not await item.lock_for_update(is_archived=False):
            raise NotFoundError(detail=f"{numbering.label} not found")

    async def _delete_and_renumber(self, *, item: _NumberedItem, numbering: _Numbering) -> None:
        """Lock the item and shift siblings above it down by one. Call inside a transaction.

        Raises:
            NotFoundError: If the item or its parent was archived after the item was loaded.
        """
        await self._lock_numbered_item(item=item, numbering=numbering)
        await numbering.model.filter(
            **{numbering.parent_field: numbering.parent_id(item)},
            number__gt=item.number,
            is_archived=False,
        ).update(number=F("number") - 1)

    async def _renumber(
        self, *, item: _NumberedItem, numbering: _Numbering, new_number: int
    ) -> int:
        """Move an item to a new position and shift siblings to maintain contiguous numbering.

        Returns:
            The item's number before the move, read under lock.

        Raises:
            NotFoundError: If the item or its parent was archived after the item was loaded.
            ValidationError: If the new number is outside the sequence.
        """
        async with in_transaction():
            await self._lock_numbered_item(item=item, numbering=numbering)
            original_number = item.number
            if new_number == original_number:
                return original_number

            siblings = numbering.model.filter(
                **{numbering.parent_field: numbering.parent_id(item)}, is_archived=False
            )
            sibling_count = await siblings.count()
            if new_number > sibling_count:
                msg = f"New number {new_number} is greater than the number of {numbering.plural} ({sibling_count})"
                raise ValidationError(msg)
            if new_number < 1:
                msg = f"New number {new_number} is less than 1"
                raise ValidationError(msg)

            if new_number > original_number:
                # Moving forward: shift items in (old, new] down by 1
                await (
                    siblings.filter(number__gt=original_number, number__lte=new_number)
                    .exclude(id=item.id)
                    .update(number=F("number") - 1)
                )
            else:
                # Moving backward: shift items in [new, old) up by 1
                await (
                    siblings.filter(number__gte=new_number, number__lt=original_number)
                    .exclude(id=item.id)
                    .update(number=F("number") + 1)
                )
            await numbering.model.filter(id=item.id).update(number=new_number)
        item.number = new_number
        return original_number
