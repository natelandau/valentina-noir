"""Character notes controller."""

from __future__ import annotations

from typing import Annotated

from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.models import Character, Note  # noqa: TC001
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination  # noqa: TC001
from vapi.openapi.tags import APITags

from . import dto
from .base import BaseNoteController


class CharacterNoteController(BaseNoteController):
    """Character notes controller."""

    tags = [APITags.CHARACTERS_NOTES.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "character": Provide(deps.provide_character_by_id_and_company),
        "note": Provide(deps.provide_note_by_id),
    }

    @property
    def parent_name(self) -> str:
        """Return the parent entity name."""
        return "character"

    @get(
        path=urls.Characters.NOTES,
        summary="List character notes",
        operation_id="listCharacterNotes",
        description="Retrieve a paginated list of notes attached to a character. Notes can contain backstory elements, session events, or storyteller comments.",
        cache=True,
    )
    async def list_character_notes(
        self,
        character: Character,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[Note]:
        """List all character notes."""
        return await self._list_notes(character.id, limit, offset)

    @get(
        path=urls.Characters.NOTE_DETAIL,
        summary="Get character note",
        operation_id="getCharacterNote",
        description="Retrieve a specific note attached to a character.",
        cache=True,
    )
    async def get_note(self, note: Note) -> Note:
        """Get a note by ID."""
        return await self._get_note(note)

    @post(
        path=urls.Characters.NOTE_CREATE,
        summary="Create character note",
        operation_id="createCharacterNote",
        description="Attach a new note to a character. Notes support markdown formatting for rich text content.",
        dto=dto.NotePostDTO,
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def create_note(self, character: Character, data: DTOData[Note]) -> Note:
        """Create a new note."""
        return await self._create_note(character.id, data)

    @patch(
        path=urls.Characters.NOTE_UPDATE,
        summary="Update character note",
        operation_id="updateCharacterNote",
        description="Modify a character note's content. Only include fields that need to be changed.",
        dto=dto.NotePatchDTO,
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def update_note(self, note: Note, data: DTOData[Note]) -> Note:
        """Update a note by ID."""
        return await self._update_note(note, data)

    @delete(
        path=urls.Characters.NOTE_DELETE,
        summary="Delete character note",
        operation_id="deleteCharacterNote",
        description="Remove a note from a character. This action cannot be undone.",
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def delete_note(self, note: Note) -> None:
        """Delete a note by ID."""
        await self._delete_note(note)
