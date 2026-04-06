"""Notes DTOs."""

from datetime import datetime
from uuid import UUID

import msgspec

from vapi.db.sql_models.notes import Note


class NoteCreate(msgspec.Struct):
    """Request body for creating a note."""

    title: str
    content: str = ""


class NotePatch(msgspec.Struct):
    """Request body for updating a note."""

    title: str | msgspec.UnsetType = msgspec.UNSET
    content: str | msgspec.UnsetType = msgspec.UNSET


class NoteResponse(msgspec.Struct):
    """Response body for a note."""

    id: UUID
    date_created: datetime
    date_modified: datetime
    title: str
    content: str
    company_id: UUID
    campaign_id: UUID | None
    book_id: UUID | None
    chapter_id: UUID | None
    character_id: UUID | None
    user_id: UUID | None

    @classmethod
    def from_model(cls, m: Note) -> "NoteResponse":
        """Convert a Tortoise Note to a response Struct."""
        return cls(
            id=m.id,
            date_created=m.date_created,
            date_modified=m.date_modified,
            title=m.title,
            content=m.content or "",
            company_id=m.company_id,  # type: ignore[attr-defined]
            campaign_id=m.campaign_id,  # type: ignore[attr-defined]
            book_id=m.book_id,  # type: ignore[attr-defined]
            chapter_id=m.chapter_id,  # type: ignore[attr-defined]
            character_id=m.character_id,  # type: ignore[attr-defined]
            user_id=m.user_id,  # type: ignore[attr-defined]
        )
