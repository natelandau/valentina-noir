"""Notes model."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from pydantic import Field

from vapi.db.models.base import BaseDocument


class Note(BaseDocument):
    """Note model."""

    title: Annotated[str, Field(min_length=3, max_length=50)]
    content: Annotated[str, Field(min_length=3)]

    # Note is attached to
    user_id: PydanticObjectId | None = None
    campaign_id: PydanticObjectId | None = None
    book_id: PydanticObjectId | None = None
    chapter_id: PydanticObjectId | None = None
    character_id: PydanticObjectId | None = None
