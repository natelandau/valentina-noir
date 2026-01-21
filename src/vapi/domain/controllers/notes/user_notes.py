"""User notes controller."""

from __future__ import annotations

from typing import Annotated

from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.models import Company, Note, User  # noqa: TC001
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination  # noqa: TC001
from vapi.openapi.tags import APITags

from . import dto
from .base import BaseNoteController


class UserNoteController(BaseNoteController):
    """User notes controller."""

    tags = [APITags.USERS_NOTES.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "developer": Provide(deps.provide_developer_from_request),
        "note": Provide(deps.provide_note_by_id),
    }

    @property
    def parent_name(self) -> str:
        """Return the parent entity name."""
        return "user"

    @get(
        path=urls.Users.LIST_NOTES,
        summary="List user notes",
        operation_id="listUserNotes",
        description="Retrieve a paginated list of notes attached to a user. Notes can be used to track player-specific information across sessions.",
        cache=True,
    )
    async def list_user_notes(
        self,
        *,
        user: User,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[Note]:
        """List all user notes."""
        return await self._list_notes(user.id, limit, offset)

    @get(
        path=urls.Users.NOTE_DETAIL,
        summary="Get user note",
        operation_id="getUserNote",
        description="Retrieve a specific note attached to a user.",
        cache=True,
    )
    async def get_user_note(self, *, note: Note) -> Note:
        """Get a user note by ID."""
        return await self._get_note(note)

    @post(
        path=urls.Users.NOTE_CREATE,
        summary="Create user note",
        operation_id="createUserNote",
        description="Attach a new note to a user. Notes support markdown formatting for rich text content.",
        dto=dto.NotePostDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def create_user_note(self, *, company: Company, user: User, data: DTOData[Note]) -> Note:
        """Create a user note."""
        return await self._create_note(company_id=company.id, parent_id=user.id, data=data)

    @patch(
        path=urls.Users.NOTE_UPDATE,
        summary="Update user note",
        operation_id="updateUserNote",
        description="Modify a user note's content. Only include fields that need to be changed.",
        dto=dto.NotePatchDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def update_user_note(self, note: Note, data: DTOData[Note]) -> Note:
        """Update a user note by ID."""
        return await self._update_note(note, data)

    @delete(
        path=urls.Users.NOTE_DELETE,
        summary="Delete user note",
        operation_id="deleteUserNote",
        description="Remove a note from a user. This action cannot be undone.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def delete_user_note(self, *, note: Note) -> None:
        """Delete a user note by ID."""
        await self._delete_note(note)
