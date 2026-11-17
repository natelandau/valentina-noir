"""Unit tests for vapi.lib.patch.save_active_patch."""

from collections.abc import Callable
from typing import Any

import pytest

from vapi.db.sql_models.base import new_uuid
from vapi.db.sql_models.notes import Note
from vapi.domain.controllers.notes.dto import NotePatch
from vapi.lib.exceptions import NotFoundError
from vapi.lib.patch import archive_active, save_active_patch
from vapi.utils.time import time_now

pytestmark = pytest.mark.anyio


async def _cascade_archive(model: type[Note], row_id: object) -> object:
    """Archive a row the way a parent-delete cascade does: a bulk UPDATE with a batch id."""
    batch_id = new_uuid()
    await model.filter(id=row_id).update(
        is_archived=True, archive_date=time_now(), archive_batch_id=batch_id
    )
    return batch_id


class TestSaveActivePatch:
    """Test that a patch never resurrects or overwrites a row changed after it was loaded."""

    async def test_stale_note_archived_by_cascade_stays_archived(
        self, company_factory: Callable[..., Any], note_factory: Callable[..., Any]
    ) -> None:
        """Verify a patch on a note archived after load raises 404 and keeps the archive."""
        # Given a note loaded by a request, then archived by a concurrent parent delete
        note = await note_factory(company=await company_factory())
        stale = await Note.get(id=note.id)
        batch_id = await _cascade_archive(Note, note.id)

        # When the request saves its patch to the stale instance
        with pytest.raises(NotFoundError, match="Note not found"):
            await save_active_patch(stale, NotePatch(title="edited"), label="Note")

        # Then the note stays archived in the cascade batch and keeps its title
        row = await Note.get(id=note.id)
        assert row.is_archived is True
        assert row.archive_batch_id == batch_id
        assert row.archive_date is not None
        assert row.title == note.title

    async def test_writes_only_patched_columns(
        self, company_factory: Callable[..., Any], note_factory: Callable[..., Any]
    ) -> None:
        """Verify a patch keeps a column another writer changed after the row was loaded."""
        # Given a stale note whose content was changed concurrently
        note = await note_factory(company=await company_factory(), content="original content")
        stale = await Note.get(id=note.id)
        await Note.filter(id=note.id).update(content="concurrent content")

        # When the request patches only the title
        changes = await save_active_patch(stale, NotePatch(title="edited title"), label="Note")

        # Then the title is written, the concurrent content survives, and the instance is fresh
        row = await Note.get(id=note.id)
        assert changes == {"title": {"old": note.title, "new": "edited title"}}
        assert row.title == "edited title"
        assert row.content == "concurrent content"
        assert stale.content == "concurrent content"

    async def test_empty_patch_on_archived_row_raises(
        self, company_factory: Callable[..., Any], note_factory: Callable[..., Any]
    ) -> None:
        """Verify an empty patch still refuses a row archived after load."""
        # Given a stale note archived by a cascade
        note = await note_factory(company=await company_factory())
        stale = await Note.get(id=note.id)
        await _cascade_archive(Note, note.id)

        # When/Then saving an empty patch raises NotFoundError
        with pytest.raises(NotFoundError):
            await save_active_patch(stale, NotePatch(), label="Note")


class TestArchiveActive:
    """Test that a soft delete never overwrites a row changed after it was loaded."""

    async def test_stale_note_archived_by_cascade_keeps_batch(
        self, company_factory: Callable[..., Any], note_factory: Callable[..., Any]
    ) -> None:
        """Verify deleting a note archived after load raises 404 and keeps the cascade batch."""
        # Given a note loaded by a request, then archived by a concurrent parent delete
        note = await note_factory(company=await company_factory())
        stale = await Note.get(id=note.id)
        batch_id = await _cascade_archive(Note, note.id)

        # When/Then the delete raises NotFoundError
        with pytest.raises(NotFoundError, match="Note not found"):
            await archive_active(stale, label="Note")

        # And the note stays in the cascade batch
        row = await Note.get(id=note.id)
        assert row.is_archived is True
        assert row.archive_batch_id == batch_id

    async def test_archives_without_overwriting_other_columns(
        self, company_factory: Callable[..., Any], note_factory: Callable[..., Any]
    ) -> None:
        """Verify a delete archives the row and keeps a column changed after load."""
        # Given a stale note whose content was changed concurrently
        note = await note_factory(company=await company_factory(), content="original content")
        stale = await Note.get(id=note.id)
        await Note.filter(id=note.id).update(content="concurrent content")

        # When the request deletes it
        await archive_active(stale, label="Note")

        # Then it is archived with stamps and the concurrent content survives
        row = await Note.get(id=note.id)
        assert row.is_archived is True
        assert row.archive_batch_id is not None
        assert row.content == "concurrent content"
