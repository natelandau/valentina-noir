"""Campaign book notes controller."""

from __future__ import annotations

from typing import Annotated

from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.models import CampaignBook, Note  # noqa: TC001
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination  # noqa: TC001
from vapi.openapi.tags import APITags

from . import dto
from .base import BaseNoteController


class CampaignBookNoteController(BaseNoteController):
    """Campaign notes controller."""

    tags = [APITags.CAMPAIGN_BOOK_NOTES.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "campaign": Provide(deps.provide_campaign_by_id),
        "book": Provide(deps.provide_campaign_book_by_id),
        "note": Provide(deps.provide_note_by_id),
    }

    @property
    def parent_name(self) -> str:
        """Return the parent entity name."""
        return "book"

    @get(
        path=urls.Campaigns.BOOK_NOTES,
        summary="List book notes",
        operation_id="listBookNotes",
        description="Retrieve a paginated list of notes attached to a book. Notes can contain session summaries, plot points, or other book-level information.",
        cache=True,
    )
    async def list_book_notes(
        self,
        *,
        book: CampaignBook,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[Note]:
        """List all campaign notes."""
        return await self._list_notes(book.id, limit, offset)

    @get(
        path=urls.Campaigns.BOOK_NOTE_DETAIL,
        summary="Get book note",
        operation_id="getBookNote",
        description="Retrieve a specific note attached to a book.",
        cache=True,
    )
    async def get_book_note(self, *, note: Note) -> Note:
        """Get a book note by ID."""
        return await self._get_note(note)

    @post(
        path=urls.Campaigns.BOOK_NOTE_CREATE,
        summary="Create book note",
        operation_id="createBookNote",
        description="Attach a new note to a book. Notes support markdown formatting for rich text content.",
        dto=dto.NotePostDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def create_book_note(self, *, book: CampaignBook, data: DTOData[Note]) -> Note:
        """Create a campaign note."""
        return await self._create_note(book.id, data)

    @patch(
        path=urls.Campaigns.BOOK_NOTE_UPDATE,
        summary="Update book note",
        operation_id="updateBookNote",
        description="Modify a book note's content. Only include fields that need to be changed.",
        dto=dto.NotePatchDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def update_book_note(self, note: Note, data: DTOData[Note]) -> Note:
        """Update a campaign note by ID."""
        return await self._update_note(note, data)

    @delete(
        path=urls.Campaigns.BOOK_NOTE_DELETE,
        summary="Delete book note",
        operation_id="deleteBookNote",
        description="Remove a note from a book. This action cannot be undone.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def delete_book_note(self, *, note: Note) -> None:
        """Delete a campaign note by ID."""
        await self._delete_note(note)
