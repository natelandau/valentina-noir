"""Campaign book notes controller."""

from typing import Annotated

from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.sql_models.campaign import CampaignBook
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.notes import Note
from vapi.domain import hooks, pg_deps, urls
from vapi.domain.paginator import OffsetPagination
from vapi.openapi.tags import APITags

from . import docs, dto
from .base import BaseNoteController


class CampaignBookNoteController(BaseNoteController):
    """Campaign book notes controller."""

    tags = [APITags.CAMPAIGN_BOOK_NOTES.name]
    dependencies = {
        "company": Provide(pg_deps.provide_pg_company_by_id),
        "user": Provide(pg_deps.provide_user_by_id_and_company),
        "campaign": Provide(pg_deps.provide_campaign_by_id),
        "book": Provide(pg_deps.provide_campaign_book_by_id),
        "note": Provide(pg_deps.provide_note_by_id),
    }

    @property
    def parent_name(self) -> str:
        """Return the parent entity name."""
        return "book"

    @get(
        path=urls.Campaigns.BOOK_NOTES,
        summary="List book notes",
        operation_id="listBookNotes",
        description=docs.LIST_NOTES_DESCRIPTION,
        cache=True,
    )
    async def list_book_notes(
        self,
        *,
        book: CampaignBook,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[dto.NoteResponse]:
        """List all book notes."""
        return await self._list_notes(book.id, limit, offset)

    @get(
        path=urls.Campaigns.BOOK_NOTE_DETAIL,
        summary="Get book note",
        operation_id="getBookNote",
        description=docs.GET_NOTE_DESCRIPTION,
        cache=True,
    )
    async def get_book_note(self, *, note: Note) -> dto.NoteResponse:
        """Get a book note by ID."""
        return await self._get_note(note)

    @post(
        path=urls.Campaigns.BOOK_NOTE_CREATE,
        summary="Create book note",
        operation_id="createBookNote",
        description=docs.CREATE_NOTE_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def create_book_note(
        self, *, company: Company, book: CampaignBook, data: dto.NoteCreate
    ) -> dto.NoteResponse:
        """Create a book note."""
        return await self._create_note(company_id=company.id, parent_id=book.id, data=data)

    @patch(
        path=urls.Campaigns.BOOK_NOTE_UPDATE,
        summary="Update book note",
        operation_id="updateBookNote",
        description=docs.UPDATE_NOTE_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def update_book_note(self, note: Note, data: dto.NotePatch) -> dto.NoteResponse:
        """Update a book note by ID."""
        return await self._update_note(note, data)

    @delete(
        path=urls.Campaigns.BOOK_NOTE_DELETE,
        summary="Delete book note",
        operation_id="deleteBookNote",
        description=docs.DELETE_NOTE_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def delete_book_note(self, *, note: Note) -> None:
        """Delete a book note by ID."""
        await self._delete_note(note)
