"""Campaign chapter notes controller."""

from typing import Annotated

from litestar import Request
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.sql_models.campaign import CampaignChapter
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.notes import Note
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.openapi.tags import APITags

from . import docs, dto
from .base import BaseNoteController


class CampaignChapterNoteController(BaseNoteController):
    """Campaign chapter notes controller."""

    tags = [APITags.CAMPAIGN_CHAPTER_NOTES.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "campaign": Provide(deps.provide_campaign_by_id),
        "book": Provide(deps.provide_campaign_book_by_id),
        "chapter": Provide(deps.provide_campaign_chapter_by_id),
        "note": Provide(deps.provide_note_by_id),
    }

    @property
    def parent_name(self) -> str:
        """Return the parent entity name."""
        return "chapter"

    @get(
        path=urls.Campaigns.CHAPTER_NOTES,
        summary="List chapter notes",
        operation_id="listChapterNotes",
        description=docs.LIST_NOTES_DESCRIPTION,
        cache=True,
    )
    async def list_chapter_notes(
        self,
        *,
        chapter: CampaignChapter,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[dto.NoteResponse]:
        """List all chapter notes."""
        return await self._list_notes(chapter.id, limit, offset)

    @get(
        path=urls.Campaigns.CHAPTER_NOTE_DETAIL,
        summary="Get chapter note",
        operation_id="getChapterNote",
        description=docs.GET_NOTE_DESCRIPTION,
        cache=True,
    )
    async def get_chapter_note(self, *, chapter: CampaignChapter, note: Note) -> dto.NoteResponse:
        """Get a chapter note by ID."""
        return await self._get_note(note, chapter.id)

    @post(
        path=urls.Campaigns.CHAPTER_NOTE_CREATE,
        summary="Create chapter note",
        operation_id="createChapterNote",
        description=docs.CREATE_NOTE_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def create_chapter_note(
        self, *, request: Request, company: Company, chapter: CampaignChapter, data: dto.NoteCreate
    ) -> dto.NoteResponse:
        """Create a chapter note."""
        return await self._create_note(
            request=request, company_id=company.id, parent_id=chapter.id, data=data
        )

    @patch(
        path=urls.Campaigns.CHAPTER_NOTE_UPDATE,
        summary="Update chapter note",
        operation_id="updateChapterNote",
        description=docs.UPDATE_NOTE_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def update_chapter_note(
        self, request: Request, chapter: CampaignChapter, note: Note, data: dto.NotePatch
    ) -> dto.NoteResponse:
        """Update a chapter note by ID."""
        return await self._update_note(request=request, note=note, parent_id=chapter.id, data=data)

    @delete(
        path=urls.Campaigns.CHAPTER_NOTE_DELETE,
        summary="Delete chapter note",
        operation_id="deleteChapterNote",
        description=docs.DELETE_NOTE_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def delete_chapter_note(
        self, *, request: Request, chapter: CampaignChapter, note: Note
    ) -> None:
        """Delete a chapter note by ID."""
        await self._delete_note(request=request, note=note, parent_id=chapter.id)
