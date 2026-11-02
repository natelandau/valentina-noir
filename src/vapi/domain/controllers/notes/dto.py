"""Notes DTOs."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

import msgspec

from vapi.db.sql_models.notes import Note
from vapi.domain.controllers.request_types import Name3to50

NoteContent = Annotated[str, msgspec.Meta(min_length=3)]


class NoteCreate(msgspec.Struct):
    """Request body for creating a note."""

    title: Name3to50
    content: NoteContent


class NotePatch(msgspec.Struct):
    """Request body for updating a note."""

    title: Name3to50 | msgspec.UnsetType = msgspec.UNSET
    content: NoteContent | msgspec.UnsetType = msgspec.UNSET


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
            company_id=m.company_id,  # ty:ignore[unresolved-attribute]
            campaign_id=m.campaign_id,  # ty:ignore[unresolved-attribute]
            book_id=m.book_id,  # ty:ignore[unresolved-attribute]
            chapter_id=m.chapter_id,  # ty:ignore[unresolved-attribute]
            character_id=m.character_id,  # ty:ignore[unresolved-attribute]
            user_id=m.user_id,  # ty:ignore[unresolved-attribute]
        )
