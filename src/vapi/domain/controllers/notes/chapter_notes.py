"""Campaign chapter notes controller."""

from __future__ import annotations

from typing import Annotated

from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.models import CampaignChapter, Company, Note  # noqa: TC001
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination  # noqa: TC001
from vapi.openapi.tags import APITags

from . import docs, dto
from .base import BaseNoteController


class CampaignChapterNoteController(BaseNoteController):
    """Campaign notes controller."""

    tags = [APITags.CAMPAIGN_CHAPTER_NOTES.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
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
    ) -> OffsetPagination[Note]:
        """List all chapter notes."""
        return await self._list_notes(chapter.id, limit, offset)

    @get(
        path=urls.Campaigns.CHAPTER_NOTE_DETAIL,
        summary="Get chapter note",
        operation_id="getChapterNote",
        description=docs.GET_NOTE_DESCRIPTION,
        cache=True,
    )
    async def get_chapter_note(self, *, note: Note) -> Note:
        """Get a chapter note by ID."""
        return await self._get_note(note)

    @post(
        path=urls.Campaigns.CHAPTER_NOTE_CREATE,
        summary="Create chapter note",
        operation_id="createChapterNote",
        description=docs.CREATE_NOTE_DESCRIPTION,
        dto=dto.NotePostDTO,
        after_response=hooks.post_data_update_hook,
    )
    async def create_chapter_note(
        self, *, company: Company, chapter: CampaignChapter, data: DTOData[Note]
    ) -> Note:
        """Create a chapter note."""
        return await self._create_note(company_id=company.id, parent_id=chapter.id, data=data)

    @patch(
        path=urls.Campaigns.CHAPTER_NOTE_UPDATE,
        summary="Update chapter note",
        operation_id="updateChapterNote",
        description=docs.UPDATE_NOTE_DESCRIPTION,
        dto=dto.NotePatchDTO,
        after_response=hooks.post_data_update_hook,
    )
    async def update_chapter_note(self, note: Note, data: DTOData[Note]) -> Note:
        """Update a chapter note by ID."""
        return await self._update_note(note, data)

    @delete(
        path=urls.Campaigns.CHAPTER_NOTE_DELETE,
        summary="Delete chapter note",
        operation_id="deleteChapterNote",
        description=docs.DELETE_NOTE_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def delete_chapter_note(self, *, note: Note) -> None:
        """Delete a chapter note by ID."""
        await self._delete_note(note)
