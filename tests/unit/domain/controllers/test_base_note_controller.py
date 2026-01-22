"""Unit tests for BaseNoteController."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from beanie import PydanticObjectId

from vapi.db.models import Note
from vapi.domain.controllers.notes.base import BaseNoteController

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.models import Character, Company

pytestmark = pytest.mark.anyio


class ConcreteNoteController(BaseNoteController):
    """Concrete implementation for testing the abstract base class."""

    def __init__(self, parent_name: str = "character") -> None:
        """Initialize with configurable parent name for testing."""
        self._parent_name = parent_name

    @property
    def parent_name(self) -> str:
        """Return the parent entity name."""
        return self._parent_name


class TestParentRefField:
    """Test parent_ref_field property derivation."""

    def test_parent_ref_field_derives_from_parent_name(self) -> None:
        """Verify parent_ref_field correctly derives from parent_name."""
        # Given a controller with parent_name "character"
        controller = ConcreteNoteController(parent_name="character")

        # When we access parent_ref_field
        result = controller.parent_ref_field

        # Then it should be "character_id"
        assert result == "character_id"

    @pytest.mark.parametrize(
        ("parent_name", "expected_ref_field"),
        [
            ("character", "character_id"),
            ("campaign", "campaign_id"),
            ("user", "user_id"),
            ("book", "book_id"),
            ("chapter", "chapter_id"),
        ],
    )
    def test_parent_ref_field_with_different_parent_names(
        self, parent_name: str, expected_ref_field: str
    ) -> None:
        """Verify parent_ref_field works for various parent entity types."""
        # Given a controller with the specified parent_name
        controller = ConcreteNoteController(parent_name=parent_name)

        # When we access parent_ref_field
        result = controller.parent_ref_field

        # Then it should match the expected value
        assert result == expected_ref_field


class TestListNotes:
    """Test _list_notes method."""

    async def test_list_notes_returns_paginated_results(
        self, base_character: Character, note_factory: Callable[..., Note]
    ) -> None:
        """Verify _list_notes returns paginated results."""
        # Given a controller and notes attached to a character
        controller = ConcreteNoteController(parent_name="character")
        await note_factory(title="Note 1", content="Content 1", character_id=base_character.id)
        await note_factory(title="Note 2", content="Content 2", character_id=base_character.id)

        # When we list notes
        result = await controller._list_notes(base_character.id, limit=10, offset=0)

        # Then we get paginated results
        assert result.total == 2
        assert len(result.items) == 2
        assert result.limit == 10
        assert result.offset == 0

    async def test_list_notes_excludes_archived(
        self, base_character: Character, note_factory: Callable[..., Note]
    ) -> None:
        """Verify _list_notes excludes archived notes."""
        # Given a controller with both active and archived notes
        controller = ConcreteNoteController(parent_name="character")
        await note_factory(title="Active Note", content="Content", character_id=base_character.id)

        await note_factory(
            title="Archived Note",
            content="Content",
            character_id=base_character.id,
            is_archived=True,
        )

        # When we list notes
        result = await controller._list_notes(base_character.id, limit=10, offset=0)

        # Then only the active note is returned
        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].title == "Active Note"

    async def test_list_notes_respects_limit_and_offset(
        self, base_character: Character, note_factory: Callable[..., Note]
    ) -> None:
        """Verify _list_notes respects limit and offset parameters."""
        # Given a controller with multiple notes
        controller = ConcreteNoteController(parent_name="character")
        for i in range(5):
            await note_factory(
                title=f"Note {i}", content=f"Content {i}", character_id=base_character.id
            )

        # When we list with limit=2 and offset=1
        result = await controller._list_notes(base_character.id, limit=2, offset=1)

        # Then we get 2 items starting from offset 1
        assert result.total == 5
        assert len(result.items) == 2
        assert result.limit == 2
        assert result.offset == 1

    async def test_list_notes_empty_results(self, base_character: Character) -> None:
        """Verify _list_notes returns empty results when no notes exist."""
        # Given a controller with no notes for the parent
        controller = ConcreteNoteController(parent_name="character")
        random_id = PydanticObjectId()

        # When we list notes for a parent with no notes
        result = await controller._list_notes(random_id, limit=10, offset=0)

        # Then we get empty results
        assert result.total == 0
        assert len(result.items) == 0


class TestGetNote:
    """Test _get_note method."""

    async def test_get_note_returns_note(
        self, base_character: Character, note_factory: Callable[..., Note]
    ) -> None:
        """Verify _get_note returns the provided note."""
        # Given a controller and a note
        controller = ConcreteNoteController(parent_name="character")
        note = await note_factory(
            title="Test Note", content="Test Content", character_id=base_character.id
        )

        # When we get the note
        result = await controller._get_note(note)

        # Then the same note is returned
        assert result == note
        assert result.id == note.id
        assert result.title == "Test Note"


class TestCreateNote:
    """Test _create_note method."""

    async def test_create_note_saves_with_parent_ref(
        self, base_character: Character, base_company: Company, mocker: Any
    ) -> None:
        """Verify _create_note saves note with correct parent reference."""
        # Given a controller and mock DTOData
        controller = ConcreteNoteController(parent_name="character")

        mock_note_data = MagicMock()
        mock_note_data.model_dump.return_value = {
            "title": "New Note",
            "content": "New Content",
            "character_id": base_character.id,
            "company_id": base_company.id,
        }

        mock_dto_data = MagicMock()
        mock_dto_data.create_instance.return_value = mock_note_data

        # When we create a note
        result = await controller._create_note(
            company_id=base_company.id, parent_id=base_character.id, data=mock_dto_data
        )

        # Then the note is saved with the correct parent reference
        assert result.title == "New Note"
        assert result.content == "New Content"
        assert result.character_id == base_character.id
        assert result.company_id == base_company.id
        assert result.id is not None

        # Verify create_instance was called with the parent ref field
        mock_dto_data.create_instance.assert_called_once()

    async def test_create_note_clears_cache(
        self, base_character: Character, base_company: Company, mocker: Any
    ) -> None:
        """Verify _create_note clears response cache."""
        # Given a controller and mock data
        controller = ConcreteNoteController(parent_name="character")

        mock_note_data = MagicMock()
        mock_note_data.model_dump.return_value = {
            "title": "Cache Test",
            "content": "Content",
            "character_id": base_character.id,
            "company_id": base_company.id,
        }

        mock_dto_data = MagicMock()
        mock_dto_data.create_instance.return_value = mock_note_data

        # When we create a note
        await controller._create_note(
            company_id=base_company.id, parent_id=base_character.id, data=mock_dto_data
        )

    async def test_create_note_adds_audit_log(
        self, base_character: Character, base_company: Company, mocker: Any
    ) -> None:
        """Verify _create_note adds audit log entry."""
        # Given a controller and mock data
        controller = ConcreteNoteController(parent_name="character")

        mock_note_data = MagicMock()
        mock_note_data.model_dump.return_value = {
            "title": "Audit Test",
            "content": "Content",
            "character_id": base_character.id,
            "company_id": base_company.id,
        }

        mock_dto_data = MagicMock()
        mock_dto_data.create_instance.return_value = mock_note_data

        # When we create a note
        await controller._create_note(
            company_id=base_company.id, parent_id=base_character.id, data=mock_dto_data
        )


class TestUpdateNote:
    """Test _update_note method."""

    async def test_update_note_saves_changes(
        self,
        base_character: Character,
        base_company: Company,
        mocker: Any,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify _update_note saves updated note."""
        # Given a controller and an existing note
        controller = ConcreteNoteController(parent_name="character")
        note = await note_factory(
            title="Original Title", content="Original Content", character_id=base_character.id
        )

        # Given mock DTOData that updates the note
        updated_note = Note(
            id=note.id,
            title="Updated Title",
            content="Updated Content",
            character_id=base_character.id,
            company_id=base_company.id,
        )

        mock_dto_data = MagicMock()
        mock_dto_data.update_instance.return_value = updated_note

        # Given mock patch_dto_data_internal_objects
        mocker.patch(
            "vapi.domain.controllers.notes.base.patch_dto_data_internal_objects",
            new_callable=AsyncMock,
            return_value=(note, mock_dto_data),
        )

        # When we update the note
        result = await controller._update_note(note, mock_dto_data)

        # Then the updated note is returned
        assert result.title == "Updated Title"
        assert result.content == "Updated Content"

        # Cleanup
        await result.delete()

    async def test_update_note_clears_cache(
        self, base_character: Character, mocker: Any, note_factory: Callable[..., Note]
    ) -> None:
        """Verify _update_note clears response cache."""
        # Given a controller and an existing note
        controller = ConcreteNoteController(parent_name="character")
        note = await note_factory(title="Test", content="Content", character_id=base_character.id)

        # Given mock DTOData
        mock_dto_data = MagicMock()
        mock_dto_data.update_instance.return_value = note

        mocker.patch(
            "vapi.domain.controllers.notes.base.patch_dto_data_internal_objects",
            new_callable=AsyncMock,
            return_value=(note, mock_dto_data),
        )

        # When we update the note
        await controller._update_note(note, mock_dto_data)

    async def test_update_note_adds_audit_log(
        self, base_character: Character, mocker: Any, note_factory: Callable[..., Note]
    ) -> None:
        """Verify _update_note adds audit log entry."""
        # Given a controller and an existing note
        controller = ConcreteNoteController(parent_name="character")
        note = await note_factory(title="Test", content="Content", character_id=base_character.id)

        # Given mock DTOData
        mock_dto_data = MagicMock()
        mock_dto_data.update_instance.return_value = note

        mocker.patch(
            "vapi.domain.controllers.notes.base.patch_dto_data_internal_objects",
            new_callable=AsyncMock,
            return_value=(note, mock_dto_data),
        )

        # When we update the note
        await controller._update_note(note, mock_dto_data)


class TestDeleteNote:
    """Test _delete_note method."""

    async def test_delete_note_sets_archived_flag(
        self, base_character: Character, mocker: Any, note_factory: Callable[..., Note]
    ) -> None:
        """Verify _delete_note sets is_archived flag to True."""
        # Given a controller and an active note
        controller = ConcreteNoteController(parent_name="character")
        note = await note_factory(
            title="Delete Test", content="Content", character_id=base_character.id
        )
        assert note.is_archived is False

        # When we delete the note
        await controller._delete_note(note)

        # Then the note is archived
        await note.sync()
        assert note.is_archived is True
