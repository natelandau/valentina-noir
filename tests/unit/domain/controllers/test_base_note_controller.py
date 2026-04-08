"""Unit tests for BaseNoteController."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from vapi.db.sql_models.notes import Note
from vapi.domain.controllers.notes.base import BaseNoteController
from vapi.domain.controllers.notes.dto import NoteCreate, NotePatch
from vapi.lib.exceptions import NotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable

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
        self,
        company_factory: Callable,
        character_factory: Callable,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify _list_notes returns paginated results."""
        # Given a controller and notes attached to a character
        controller = ConcreteNoteController(parent_name="character")
        company = await company_factory()
        character = await character_factory(company=company)
        await note_factory(
            title="Note 1", content="Content 1", character=character, company=company
        )
        await note_factory(
            title="Note 2", content="Content 2", character=character, company=company
        )

        # When we list notes
        result = await controller._list_notes(character.id, limit=10, offset=0)

        # Then we get paginated results
        assert result.total == 2
        assert len(result.items) == 2
        assert result.limit == 10
        assert result.offset == 0

    async def test_list_notes_excludes_archived(
        self,
        company_factory: Callable,
        character_factory: Callable,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify _list_notes excludes archived notes."""
        # Given a controller with both active and archived notes
        controller = ConcreteNoteController(parent_name="character")
        company = await company_factory()
        character = await character_factory(company=company)
        await note_factory(
            title="Active Note", content="Content", character=character, company=company
        )
        await note_factory(
            title="Archived Note",
            content="Content",
            character=character,
            company=company,
            is_archived=True,
        )

        # When we list notes
        result = await controller._list_notes(character.id, limit=10, offset=0)

        # Then only the active note is returned
        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].title == "Active Note"

    async def test_list_notes_respects_limit_and_offset(
        self,
        company_factory: Callable,
        character_factory: Callable,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify _list_notes respects limit and offset parameters."""
        # Given a controller with multiple notes
        controller = ConcreteNoteController(parent_name="character")
        company = await company_factory()
        character = await character_factory(company=company)
        for i in range(5):
            await note_factory(
                title=f"Note {i}", content=f"Content {i}", character=character, company=company
            )

        # When we list with limit=2 and offset=1
        result = await controller._list_notes(parent_id=character.id, limit=2, offset=1)

        # Then we get 2 items starting from offset 1
        assert result.total == 5
        assert len(result.items) == 2
        assert result.limit == 2
        assert result.offset == 1

    async def test_list_notes_empty_results(self) -> None:
        """Verify _list_notes returns empty results when no notes exist."""
        # Given a controller with no notes for the parent
        controller = ConcreteNoteController(parent_name="character")
        random_id = uuid4()

        # When we list notes for a parent with no notes
        result = await controller._list_notes(parent_id=random_id, limit=10, offset=0)

        # Then we get empty results
        assert result.total == 0
        assert len(result.items) == 0


class TestGetNote:
    """Test _get_note method."""

    async def test_get_note_returns_response(
        self,
        company_factory: Callable,
        character_factory: Callable,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify _get_note returns a NoteResponse."""
        # Given a controller and a note
        controller = ConcreteNoteController(parent_name="character")
        company = await company_factory()
        character = await character_factory(company=company)
        note = await note_factory(
            title="Test Note", content="Test Content", character=character, company=company
        )

        # When we get the note
        result = await controller._get_note(note, character.id)

        # Then a response is returned with the correct data
        assert result.id == note.id
        assert result.title == "Test Note"


class TestCreateNote:
    """Test _create_note method."""

    async def test_create_note_saves_with_parent_ref(
        self,
        company_factory: Callable,
        character_factory: Callable,
    ) -> None:
        """Verify _create_note saves note with correct parent reference."""
        # Given a controller and create data
        controller = ConcreteNoteController(parent_name="character")
        company = await company_factory()
        character = await character_factory(company=company)
        data = NoteCreate(title="New Note", content="New Content")

        # When we create a note
        result = await controller._create_note(
            company_id=company.id, parent_id=character.id, data=data
        )

        # Then the note is saved with the correct parent reference
        assert result.title == "New Note"
        assert result.content == "New Content"
        assert result.character_id == character.id
        assert result.company_id == company.id
        assert result.id is not None

    async def test_create_note_persists_to_database(
        self,
        company_factory: Callable,
        character_factory: Callable,
    ) -> None:
        """Verify _create_note persists the note in the database."""
        # Given a controller and create data
        controller = ConcreteNoteController(parent_name="character")
        company = await company_factory()
        character = await character_factory(company=company)
        data = NoteCreate(title="Persist Test", content="Content")

        # When we create a note
        result = await controller._create_note(
            company_id=company.id, parent_id=character.id, data=data
        )

        # Then the note exists in the database
        db_note = await Note.filter(id=result.id).first()
        assert db_note is not None
        assert db_note.title == "Persist Test"


class TestUpdateNote:
    """Test _update_note method."""

    async def test_update_note_saves_changes(
        self,
        company_factory: Callable,
        character_factory: Callable,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify _update_note saves updated note."""
        # Given a controller and an existing note
        controller = ConcreteNoteController(parent_name="character")
        company = await company_factory()
        character = await character_factory(company=company)
        note = await note_factory(
            title="Original Title",
            content="Original Content",
            character=character,
            company=company,
        )

        # When we update the note
        data = NotePatch(title="Updated Title", content="Updated Content")
        result = await controller._update_note(note, character.id, data)

        # Then the updated note is returned
        assert result.title == "Updated Title"
        assert result.content == "Updated Content"

    async def test_update_note_partial_update(
        self,
        company_factory: Callable,
        character_factory: Callable,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify _update_note handles partial updates with UNSET fields."""
        # Given a controller and an existing note
        controller = ConcreteNoteController(parent_name="character")
        company = await company_factory()
        character = await character_factory(company=company)
        note = await note_factory(
            title="Original Title",
            content="Original Content",
            character=character,
            company=company,
        )

        # When we update only the title
        data = NotePatch(title="Updated Title")
        result = await controller._update_note(note, character.id, data)

        # Then only the title is updated
        assert result.title == "Updated Title"
        assert result.content == "Original Content"


class TestDeleteNote:
    """Test _delete_note method."""

    async def test_delete_note_sets_archived_flag(
        self,
        company_factory: Callable,
        character_factory: Callable,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify _delete_note sets is_archived flag to True."""
        # Given a controller and an active note
        controller = ConcreteNoteController(parent_name="character")
        company = await company_factory()
        character = await character_factory(company=company)
        note = await note_factory(
            title="Delete Test", content="Content", character=character, company=company
        )
        assert note.is_archived is False

        # When we delete the note
        await controller._delete_note(note, character.id)

        # Then the note is archived
        await note.refresh_from_db()
        assert note.is_archived is True


class TestParentScopingIDOR:
    """Verify cross-parent access is blocked on get/update/delete."""

    async def test_get_note_wrong_parent_raises_not_found(
        self,
        company_factory: Callable,
        character_factory: Callable,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify _get_note rejects a note whose parent FK differs from the URL parent."""
        # Given a note owned by character A, fetched via character B's URL
        controller = ConcreteNoteController(parent_name="character")
        company = await company_factory()
        character_a = await character_factory(company=company)
        character_b = await character_factory(company=company)
        note = await note_factory(character=character_a, company=company)

        # When we attempt to fetch the note under character B
        # Then a NotFoundError is raised
        with pytest.raises(NotFoundError):
            await controller._get_note(note, character_b.id)

    async def test_update_note_wrong_parent_raises_not_found(
        self,
        company_factory: Callable,
        character_factory: Callable,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify _update_note rejects cross-parent access and does not mutate the note."""
        # Given a note owned by character A
        controller = ConcreteNoteController(parent_name="character")
        company = await company_factory()
        character_a = await character_factory(company=company)
        character_b = await character_factory(company=company)
        note = await note_factory(
            title="Original", content="Original", character=character_a, company=company
        )

        # When we attempt to update under character B
        # Then NotFoundError is raised and the note is unchanged
        with pytest.raises(NotFoundError):
            await controller._update_note(
                note, character_b.id, NotePatch(title="Hacked", content="Hacked")
            )
        await note.refresh_from_db()
        assert note.title == "Original"
        assert note.content == "Original"

    async def test_delete_note_wrong_parent_raises_not_found(
        self,
        company_factory: Callable,
        character_factory: Callable,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify _delete_note rejects cross-parent access and does not archive the note."""
        # Given a note owned by character A
        controller = ConcreteNoteController(parent_name="character")
        company = await company_factory()
        character_a = await character_factory(company=company)
        character_b = await character_factory(company=company)
        note = await note_factory(character=character_a, company=company)

        # When we attempt to delete under character B
        # Then NotFoundError is raised and the note is not archived
        with pytest.raises(NotFoundError):
            await controller._delete_note(note, character_b.id)
        await note.refresh_from_db()
        assert note.is_archived is False

    async def test_get_note_archived_raises_not_found(
        self,
        company_factory: Callable,
        character_factory: Callable,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify _get_note hides soft-deleted notes even when parent matches."""
        # Given an archived note owned by character A
        controller = ConcreteNoteController(parent_name="character")
        company = await company_factory()
        character = await character_factory(company=company)
        note = await note_factory(character=character, company=company)
        note.is_archived = True
        await note.save()

        # When we fetch the note with the correct parent
        # Then NotFoundError is raised
        with pytest.raises(NotFoundError):
            await controller._get_note(note, character.id)
