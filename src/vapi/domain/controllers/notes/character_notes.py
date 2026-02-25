"""Character notes controller."""

from __future__ import annotations

from typing import Annotated

from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.models import Character, Company, Note  # noqa: TC001
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination  # noqa: TC001
from vapi.openapi.tags import APITags

from . import docs, dto
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
        description=docs.LIST_NOTES_DESCRIPTION,
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
        description=docs.GET_NOTE_DESCRIPTION,
        cache=True,
    )
    async def get_note(self, note: Note) -> Note:
        """Get a note by ID."""
        return await self._get_note(note)

    @post(
        path=urls.Characters.NOTE_CREATE,
        summary="Create character note",
        operation_id="createCharacterNote",
        description=docs.CREATE_NOTE_DESCRIPTION,
        dto=dto.NotePostDTO,
        after_response=hooks.post_data_update_hook,
    )
    async def create_note(
        self, *, company: Company, character: Character, data: DTOData[Note]
    ) -> Note:
        """Create a new note."""
        return await self._create_note(company_id=company.id, parent_id=character.id, data=data)

    @patch(
        path=urls.Characters.NOTE_UPDATE,
        summary="Update character note",
        operation_id="updateCharacterNote",
        description=docs.UPDATE_NOTE_DESCRIPTION,
        dto=dto.NotePatchDTO,
        after_response=hooks.post_data_update_hook,
    )
    async def update_note(self, note: Note, data: DTOData[Note]) -> Note:
        """Update a note by ID."""
        return await self._update_note(note, data)

    @delete(
        path=urls.Characters.NOTE_DELETE,
        summary="Delete character note",
        operation_id="deleteCharacterNote",
        description=docs.DELETE_NOTE_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def delete_note(self, note: Note) -> None:
        """Delete a note by ID."""
        await self._delete_note(note)
