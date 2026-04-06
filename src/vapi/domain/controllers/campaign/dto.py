"""Campaign DTOs."""

from datetime import datetime
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

import msgspec

if TYPE_CHECKING:
    from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter


# ---------------------------------------------------------------------------
# Response Structs
# ---------------------------------------------------------------------------


class CampaignResponse(msgspec.Struct):
    """Response body for a campaign."""

    id: UUID
    name: str
    description: str | None
    desperation: int
    danger: int
    company_id: UUID
    date_created: datetime
    date_modified: datetime

    @classmethod
    def from_model(cls, m: "Campaign") -> "CampaignResponse":
        """Convert a Tortoise Campaign to a response Struct."""
        return cls(
            id=m.id,
            name=m.name,
            description=m.description,
            desperation=m.desperation,
            danger=m.danger,
            company_id=m.company_id,  # type: ignore[attr-defined]
            date_created=m.date_created,
            date_modified=m.date_modified,
        )


class CampaignBookResponse(msgspec.Struct):
    """Response body for a campaign book."""

    id: UUID
    name: str
    description: str | None
    number: int
    campaign_id: UUID
    date_created: datetime
    date_modified: datetime

    @classmethod
    def from_model(cls, m: "CampaignBook") -> "CampaignBookResponse":
        """Convert a Tortoise CampaignBook to a response Struct."""
        return cls(
            id=m.id,
            name=m.name,
            description=m.description,
            number=m.number,
            campaign_id=m.campaign_id,  # type: ignore[attr-defined]
            date_created=m.date_created,
            date_modified=m.date_modified,
        )


class CampaignChapterResponse(msgspec.Struct):
    """Response body for a campaign chapter."""

    id: UUID
    name: str
    description: str | None
    number: int
    book_id: UUID
    date_created: datetime
    date_modified: datetime

    @classmethod
    def from_model(cls, m: "CampaignChapter") -> "CampaignChapterResponse":
        """Convert a Tortoise CampaignChapter to a response Struct."""
        return cls(
            id=m.id,
            name=m.name,
            description=m.description,
            number=m.number,
            book_id=m.book_id,  # type: ignore[attr-defined]
            date_created=m.date_created,
            date_modified=m.date_modified,
        )


# ---------------------------------------------------------------------------
# Request Structs
# ---------------------------------------------------------------------------


class CampaignCreate(msgspec.Struct):
    """Request body for creating a campaign."""

    name: str
    description: str | None = None
    desperation: int = 0
    danger: int = 0


class CampaignPatch(msgspec.Struct):
    """Request body for partially updating a campaign.

    All fields use UNSET as default to distinguish 'not sent' from 'sent as null'.
    """

    name: str | msgspec.UnsetType = msgspec.UNSET
    description: str | None | msgspec.UnsetType = msgspec.UNSET
    desperation: int | msgspec.UnsetType = msgspec.UNSET
    danger: int | msgspec.UnsetType = msgspec.UNSET


class CampaignBookCreate(msgspec.Struct):
    """Request body for creating a campaign book."""

    name: str
    description: str | None = None


class CampaignBookPatch(msgspec.Struct):
    """Request body for partially updating a campaign book.

    All fields use UNSET as default to distinguish 'not sent' from 'sent as null'.
    """

    name: str | msgspec.UnsetType = msgspec.UNSET
    description: str | None | msgspec.UnsetType = msgspec.UNSET


class CampaignChapterCreate(msgspec.Struct):
    """Request body for creating a campaign chapter."""

    name: str
    description: str | None = None


class CampaignChapterPatch(msgspec.Struct):
    """Request body for partially updating a campaign chapter.

    All fields use UNSET as default to distinguish 'not sent' from 'sent as null'.
    """

    name: str | msgspec.UnsetType = msgspec.UNSET
    description: str | None | msgspec.UnsetType = msgspec.UNSET


class BookChapterNumber(msgspec.Struct):
    """Request body for renumbering a book or chapter."""

    number: Annotated[int, msgspec.Meta(ge=1)]
