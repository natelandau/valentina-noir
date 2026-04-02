"""User notes controller."""

from typing import Annotated

from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.sql_models.company import Company
from vapi.db.sql_models.notes import Note
from vapi.db.sql_models.user import User
from vapi.domain import hooks, pg_deps, urls
from vapi.domain.paginator import OffsetPagination
from vapi.openapi.tags import APITags

from . import docs, dto
from .base import BaseNoteController


class UserNoteController(BaseNoteController):
    """User notes controller."""

    tags = [APITags.USERS_NOTES.name]
    dependencies = {
        "company": Provide(pg_deps.provide_pg_company_by_id),
        "user": Provide(pg_deps.provide_user_by_id_and_company),
        "developer": Provide(pg_deps.provide_developer_from_request),
        "note": Provide(pg_deps.provide_note_by_id),
    }

    @property
    def parent_name(self) -> str:
        """Return the parent entity name."""
        return "user"

    @get(
        path=urls.Users.LIST_NOTES,
        summary="List user notes",
        operation_id="listUserNotes",
        description=docs.LIST_NOTES_DESCRIPTION,
        cache=True,
    )
    async def list_user_notes(
        self,
        *,
        user: User,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[dto.NoteResponse]:
        """List all user notes."""
        return await self._list_notes(user.id, limit, offset)

    @get(
        path=urls.Users.NOTE_DETAIL,
        summary="Get user note",
        operation_id="getUserNote",
        description=docs.GET_NOTE_DESCRIPTION,
        cache=True,
    )
    async def get_user_note(self, *, note: Note) -> dto.NoteResponse:
        """Get a user note by ID."""
        return await self._get_note(note)

    @post(
        path=urls.Users.NOTE_CREATE,
        summary="Create user note",
        operation_id="createUserNote",
        description=docs.CREATE_NOTE_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def create_user_note(
        self, *, company: Company, user: User, data: dto.NoteCreate
    ) -> dto.NoteResponse:
        """Create a user note."""
        return await self._create_note(company_id=company.id, parent_id=user.id, data=data)

    @patch(
        path=urls.Users.NOTE_UPDATE,
        summary="Update user note",
        operation_id="updateUserNote",
        description=docs.UPDATE_NOTE_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def update_user_note(self, note: Note, data: dto.NotePatch) -> dto.NoteResponse:
        """Update a user note by ID."""
        return await self._update_note(note, data)

    @delete(
        path=urls.Users.NOTE_DELETE,
        summary="Delete user note",
        operation_id="deleteUserNote",
        description=docs.DELETE_NOTE_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def delete_user_note(self, *, note: Note) -> None:
        """Delete a user note by ID."""
        await self._delete_note(note)
