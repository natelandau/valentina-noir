"""Notes DTOs."""

from __future__ import annotations

from litestar.plugins.pydantic import PydanticDTO

from vapi.db.models import Note
from vapi.lib.dto import dto_config


class NotePostDTO(PydanticDTO[Note]):
    """Note create DTO."""

    config = dto_config(
        exclude={
            "id",
            "date_created",
            "date_modified",
            "character_id",
            "company_id",
            "campaign_id",
            "book_id",
            "chapter_id",
            "user_id",
        }
    )


class NotePatchDTO(PydanticDTO[Note]):
    """Note update DTO."""

    config = dto_config(
        exclude={
            "id",
            "date_created",
            "date_modified",
            "character_id",
            "company_id",
            "campaign_id",
            "book_id",
            "chapter_id",
            "user_id",
        }
    )


class NoteResponseDTO(PydanticDTO[Note]):
    """Note response DTO."""

    config = dto_config(
        exclude={
            "character_id",
            "company_id",
            "campaign_id",
            "book_id",
            "chapter_id",
            "user_id",
        }
    )
