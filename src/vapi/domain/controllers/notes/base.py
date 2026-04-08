"""Base notes controller with shared CRUD logic."""

from abc import ABC, abstractmethod
from uuid import UUID

import msgspec
from litestar.controller import Controller

from vapi.db.sql_models.notes import Note
from vapi.domain.paginator import OffsetPagination
from vapi.lib.exceptions import NotFoundError
from vapi.lib.guards import developer_company_user_guard, user_not_unapproved_guard

from . import dto


class BaseNoteController(Controller, ABC):
    """Abstract base controller for note CRUD operations."""

    guards = [developer_company_user_guard, user_not_unapproved_guard]

    @property
    @abstractmethod
    def parent_name(self) -> str:
        """Return the parent entity name (e.g., 'character', 'campaign', 'user')."""
        ...

    @property
    def parent_ref_field(self) -> str:
        """Return the FK field name (e.g., 'character_id')."""
        return f"{self.parent_name}_id"

    def _assert_belongs_to_parent(self, note: Note, parent_id: UUID) -> None:
        # Return 404 rather than 403 so callers cannot probe for note IDs that
        # exist under a different parent.
        if getattr(note, self.parent_ref_field) != parent_id or note.is_archived:
            raise NotFoundError(detail="Note not found")

    async def _list_notes(
        self,
        parent_id: UUID,
        limit: int = 10,
        offset: int = 0,
    ) -> OffsetPagination[dto.NoteResponse]:
        """List all notes for a parent entity."""
        filters = {self.parent_ref_field: parent_id, "is_archived": False}
        qs = Note.filter(**filters)
        count = await qs.count()
        notes = await qs.offset(offset).limit(limit)
        return OffsetPagination(
            items=[dto.NoteResponse.from_model(n) for n in notes],
            limit=limit,
            offset=offset,
            total=count,
        )

    async def _get_note(self, note: Note, parent_id: UUID) -> dto.NoteResponse:
        """Get a single note, verifying it belongs to the parent in the URL path."""
        self._assert_belongs_to_parent(note, parent_id)
        return dto.NoteResponse.from_model(note)

    async def _create_note(
        self,
        company_id: UUID,
        parent_id: UUID,
        data: dto.NoteCreate,
    ) -> dto.NoteResponse:
        """Create a new note attached to a parent entity."""
        create_kwargs = {
            "title": data.title,
            "content": data.content,
            "company_id": company_id,
            self.parent_ref_field: parent_id,
        }
        note = await Note.create(**create_kwargs)  # type: ignore[arg-type]
        return dto.NoteResponse.from_model(note)

    async def _update_note(
        self,
        note: Note,
        parent_id: UUID,
        data: dto.NotePatch,
    ) -> dto.NoteResponse:
        """Update an existing note, verifying it belongs to the parent in the URL path."""
        self._assert_belongs_to_parent(note, parent_id)
        if not isinstance(data.title, msgspec.UnsetType):
            note.title = data.title
        if not isinstance(data.content, msgspec.UnsetType):
            note.content = data.content
        await note.save()
        return dto.NoteResponse.from_model(note)

    async def _delete_note(self, note: Note, parent_id: UUID) -> None:
        """Soft-delete a note, verifying it belongs to the parent in the URL path."""
        self._assert_belongs_to_parent(note, parent_id)
        note.is_archived = True
        await note.save()
