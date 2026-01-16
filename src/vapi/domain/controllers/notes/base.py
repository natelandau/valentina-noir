"""Base notes controller with shared CRUD logic."""

from __future__ import annotations

from abc import ABC, abstractmethod

from beanie import PydanticObjectId  # noqa: TC002
from litestar.controller import Controller
from litestar.dto import DTOData  # noqa: TC002
from pydantic import ValidationError as PydanticValidationError

from vapi.db.models import Note
from vapi.domain.paginator import OffsetPagination
from vapi.domain.utils import patch_dto_data_internal_objects
from vapi.lib.guards import developer_company_user_guard
from vapi.utils.validation import raise_from_pydantic_validation_error

from . import dto


class BaseNoteController(Controller, ABC):
    """Abstract base controller for note CRUD operations.

    Subclasses must define the parent_name property which identifies the parent entity
    type (e.g., "character", "campaign", "user"). The parent_ref_field is derived
    automatically as "{parent_name}_id".
    """

    guards = [developer_company_user_guard]
    return_dto = dto.NoteResponseDTO

    @property
    @abstractmethod
    def parent_name(self) -> str:
        """Return the parent entity name (e.g., 'character', 'campaign', 'user')."""
        ...

    @property
    def parent_ref_field(self) -> str:
        """Return the document reference field name (e.g., 'character_id')."""
        return f"{self.parent_name}_id"

    async def _list_notes(
        self,
        parent_id: PydanticObjectId,
        limit: int = 10,
        offset: int = 0,
    ) -> OffsetPagination[Note]:
        """List all notes for a parent entity.

        Args:
            parent_id (PydanticObjectId): The ID of the parent document.
            limit (int): Maximum number of notes to return.
            offset (int): Number of notes to skip.

        Returns:
            OffsetPagination[Note]: Paginated list of notes.
        """
        query = {self.parent_ref_field: parent_id, "is_archived": False}
        count = await Note.find(query).count()
        notes = await Note.find(query).skip(offset).limit(limit).to_list()
        return OffsetPagination(items=notes, limit=limit, offset=offset, total=count)

    async def _get_note(self, note: Note) -> Note:
        """Get a single note by ID.

        Args:
            note (Note): The note document.

        Returns:
            Note: The note document.
        """
        return note

    async def _create_note(
        self,
        parent_id: PydanticObjectId,
        data: DTOData[Note],
    ) -> Note:
        """Create a new note attached to a parent entity.

        Args:
            parent_id (PydanticObjectId): The ID of the parent document.
            data (DTOData[Note]): The note data from the request.
            request (Request): The Litestar request object.

        Returns:
            Note: The created note document.
        """
        try:
            note_data = data.create_instance(**{self.parent_ref_field: parent_id})
            note = Note(**note_data.model_dump(exclude_unset=True))
            await note.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return note

    async def _update_note(
        self,
        note: Note,
        data: DTOData[Note],
    ) -> Note:
        """Update an existing note.

        Args:
            note (Note): The note document to update.
            data (DTOData[Note]): The update data from the request.
            request (Request): The Litestar request object.

        Returns:
            Note: The updated note document.
        """
        note, data = await patch_dto_data_internal_objects(original=note, data=data)
        updated_note = data.update_instance(note)
        try:
            await updated_note.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return updated_note

    async def _delete_note(self, note: Note) -> None:
        """Soft-delete a note by archiving it.

        Args:
            note (Note): The note document to delete.
            request (Request): The Litestar request object.
        """
        note.is_archived = True
        await note.save()
