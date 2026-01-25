"""Campaign schemas."""

from __future__ import annotations

from typing import Annotated

from litestar.plugins.pydantic import PydanticDTO
from pydantic import BaseModel, Field

from vapi.db.models import Campaign, CampaignBook, CampaignChapter
from vapi.lib.dto import dto_config


class PostCampaignDTO(PydanticDTO[Campaign]):
    """Campaign post DTO."""

    config = dto_config(exclude={"id", "date_created", "date_modified", "company_id", "asset_ids"})


class PatchCampaignDTO(PydanticDTO[Campaign]):
    """Campaign patch DTO."""

    config = dto_config(
        partial=True, exclude={"id", "date_created", "date_modified", "company_id", "asset_ids"}
    )


class CampaignDTO(PydanticDTO[Campaign]):
    """Campaign return DTO."""

    config = dto_config()


class PostBookDTO(PydanticDTO[CampaignBook]):
    """Campaign book post DTO."""

    config = dto_config(
        exclude={"id", "date_created", "date_modified", "campaign_id", "number", "asset_ids"}
    )


class PatchBookDTO(PydanticDTO[CampaignBook]):
    """Campaign book patch DTO."""

    config = dto_config(
        partial=True,
        exclude={"id", "date_created", "date_modified", "campaign_id", "number", "asset_ids"},
    )


class BookDTO(PydanticDTO[CampaignBook]):
    """Campaign book return DTO."""

    config = dto_config()


class PostChapterDTO(PydanticDTO[CampaignChapter]):
    """Campaign chapter post DTO."""

    config = dto_config(
        exclude={"id", "date_created", "date_modified", "book_id", "number", "asset_ids"}
    )


class PatchChapterDTO(PydanticDTO[CampaignChapter]):
    """Campaign chapter patch DTO."""

    config = dto_config(
        partial=True,
        exclude={"id", "date_created", "date_modified", "book_id", "number", "asset_ids"},
    )


class ChapterDTO(PydanticDTO[CampaignChapter]):
    """Campaign chapter return DTO."""

    config = dto_config()


class BookChapterNumberDTO(BaseModel):
    """Book chapter number DTO."""

    number: Annotated[int, Field(ge=1)]
