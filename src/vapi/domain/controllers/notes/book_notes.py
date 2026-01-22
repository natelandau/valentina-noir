"""Campaign book notes controller."""

from __future__ import annotations

from typing import Annotated

from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.models import CampaignBook, Company, Note  # noqa: TC001
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination  # noqa: TC001
from vapi.openapi.tags import APITags

from . import docs, dto
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
        description=docs.LIST_NOTES_DESCRIPTION,
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
        description=docs.GET_NOTE_DESCRIPTION,
        cache=True,
    )
    async def get_book_note(self, *, note: Note) -> Note:
        """Get a book note by ID."""
        return await self._get_note(note)

    @post(
        path=urls.Campaigns.BOOK_NOTE_CREATE,
        summary="Create book note",
        operation_id="createBookNote",
        description=docs.CREATE_NOTE_DESCRIPTION,
        dto=dto.NotePostDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def create_book_note(
        self, *, company: Company, book: CampaignBook, data: DTOData[Note]
    ) -> Note:
        """Create a campaign note."""
        return await self._create_note(company_id=company.id, parent_id=book.id, data=data)

    @patch(
        path=urls.Campaigns.BOOK_NOTE_UPDATE,
        summary="Update book note",
        operation_id="updateBookNote",
        description=docs.UPDATE_NOTE_DESCRIPTION,
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
        description=docs.DELETE_NOTE_DESCRIPTION,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def delete_book_note(self, *, note: Note) -> None:
        """Delete a campaign note by ID."""
        await self._delete_note(note)
