"""Campaign model."""

from __future__ import annotations

from typing import Annotated, ClassVar

from beanie import PydanticObjectId  # noqa: TC002
from pydantic import BeforeValidator, Field

from vapi.constants import MAX_DANGER, MAX_DESPERATION
from vapi.lib.validation import empty_string_to_none

from .base import BaseDocument


class CampaignBase(BaseDocument):
    """Campaign base model which is inherited by campaigns, books, and chapters. This is used to keep all the documents in the same mongodb collection."""

    name: Annotated[str, Field(min_length=3, max_length=50)]
    description: Annotated[
        str | None,
        Field(min_length=3, default=None),
        BeforeValidator(empty_string_to_none),
    ]
    asset_ids: list[PydanticObjectId] = Field(default_factory=list)

    class Settings:
        """Settings for the CampaignBase model."""

        is_root = True


class CampaignChapter(CampaignBase):
    """Campaign chapter model."""

    number: int
    book_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])

    class Settings:
        """Settings for the CampaignChapter model."""

        indexes: ClassVar[list[str]] = ["book_id"]


class CampaignBook(CampaignBase):
    """Campaign book model."""

    number: int

    campaign_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])

    class Settings:
        """Settings for the CampaignBook model."""

        indexes: ClassVar[list[str]] = ["campaign_id"]


class Campaign(CampaignBase):
    """Campaign model."""

    desperation: Annotated[int | None, Field(le=MAX_DESPERATION, default=0)] = 0
    danger: Annotated[int | None, Field(le=MAX_DANGER, default=0)] = 0

    company_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])

    class Settings:
        """Settings for the Campaign model."""

        indexes: ClassVar[list[str]] = ["company_id"]
