"""Character notes controller."""

from typing import Annotated

from litestar import Request
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.sql_models.character import Character
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.notes import Note
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.openapi.tags import APITags

from . import docs, dto
from .base import BaseNoteController


class CharacterNoteController(BaseNoteController):
    """Character notes controller."""

    tags = [APITags.CHARACTERS_NOTES.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "acting_user": Provide(deps.provide_acting_user),
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
    ) -> OffsetPagination[dto.NoteResponse]:
        """List all character notes."""
        return await self._list_notes(character.id, limit, offset)

    @get(
        path=urls.Characters.NOTE_DETAIL,
        summary="Get character note",
        operation_id="getCharacterNote",
        description=docs.GET_NOTE_DESCRIPTION,
        cache=True,
    )
    async def get_note(self, character: Character, note: Note) -> dto.NoteResponse:
        """Get a note by ID."""
        return await self._get_note(note, character.id)

    @post(
        path=urls.Characters.NOTE_CREATE,
        summary="Create character note",
        operation_id="createCharacterNote",
        description=docs.CREATE_NOTE_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def create_note(
        self, *, request: Request, company: Company, character: Character, data: dto.NoteCreate
    ) -> dto.NoteResponse:
        """Create a new note."""
        return await self._create_note(
            request=request, company_id=company.id, parent_id=character.id, data=data
        )

    @patch(
        path=urls.Characters.NOTE_UPDATE,
        summary="Update character note",
        operation_id="updateCharacterNote",
        description=docs.UPDATE_NOTE_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def update_note(
        self, character: Character, note: Note, data: dto.NotePatch, request: Request
    ) -> dto.NoteResponse:
        """Update a note by ID."""
        return await self._update_note(
            note=note, parent_id=character.id, data=data, request=request
        )

    @delete(
        path=urls.Characters.NOTE_DELETE,
        summary="Delete character note",
        operation_id="deleteCharacterNote",
        description=docs.DELETE_NOTE_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def delete_note(self, request: Request, character: Character, note: Note) -> None:
        """Delete a note by ID."""
        await self._delete_note(request=request, note=note, parent_id=character.id)
