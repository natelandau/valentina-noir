"""Campaign DTOs."""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

import msgspec

if TYPE_CHECKING:
    from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter


class BookInclude(StrEnum):
    """Child resources that can be embedded in a campaign book detail response."""

    CHAPTERS = "chapters"
    NOTES = "notes"
    ASSETS = "assets"


BOOK_INCLUDE_PREFETCH_MAP: dict[BookInclude, list[str]] = {
    BookInclude.CHAPTERS: ["chapters"],
    BookInclude.NOTES: ["notes"],
    BookInclude.ASSETS: ["assets"],
}


class ChapterInclude(StrEnum):
    """Child resources that can be embedded in a campaign chapter detail response."""

    NOTES = "notes"
    ASSETS = "assets"


CHAPTER_INCLUDE_PREFETCH_MAP: dict[ChapterInclude, list[str]] = {
    ChapterInclude.NOTES: ["notes"],
    ChapterInclude.ASSETS: ["assets"],
}


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


class CampaignBookDetailResponse(CampaignBookResponse, omit_defaults=True):
    """Response body for a single campaign book with optional embedded children."""

    # Child DTO modules can't be imported at module level without circular imports,
    # so fields are typed as the msgspec.Struct base and narrowed at runtime.
    chapters: list[msgspec.Struct] | msgspec.UnsetType = msgspec.UNSET
    notes: list[msgspec.Struct] | msgspec.UnsetType = msgspec.UNSET
    assets: list[msgspec.Struct] | msgspec.UnsetType = msgspec.UNSET

    @classmethod
    def from_model(
        cls,
        m: "CampaignBook",
        includes: set[BookInclude] | None = None,
    ) -> "CampaignBookDetailResponse":
        """Convert a Tortoise CampaignBook to a detail response.

        Args:
            m: The CampaignBook model instance with relations prefetched.
            includes: Set of BookInclude values indicating which children to embed.
        """
        from vapi.domain.controllers.notes.dto import NoteResponse
        from vapi.domain.controllers.s3_assets.dto import S3AssetResponse

        includes = includes or set()
        base = CampaignBookResponse.from_model(m)
        fields: dict[str, object] = {f: getattr(base, f) for f in base.__struct_fields__}
        if BookInclude.CHAPTERS in includes:
            fields["chapters"] = [CampaignChapterResponse.from_model(c) for c in m.chapters]
        if BookInclude.NOTES in includes:
            fields["notes"] = [NoteResponse.from_model(n) for n in m.notes]
        if BookInclude.ASSETS in includes:
            fields["assets"] = [S3AssetResponse.from_model(a) for a in m.assets]

        return cls(**fields)  # type: ignore[arg-type]


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


class CampaignChapterDetailResponse(CampaignChapterResponse, omit_defaults=True):
    """Response body for a single chapter with optional embedded children."""

    notes: list[msgspec.Struct] | msgspec.UnsetType = msgspec.UNSET
    assets: list[msgspec.Struct] | msgspec.UnsetType = msgspec.UNSET

    @classmethod
    def from_model(
        cls,
        m: "CampaignChapter",
        includes: set[ChapterInclude] | None = None,
    ) -> "CampaignChapterDetailResponse":
        """Convert a CampaignChapter to a detail response with optional children."""
        from vapi.domain.controllers.notes.dto import NoteResponse
        from vapi.domain.controllers.s3_assets.dto import S3AssetResponse

        includes = includes or set()
        base = CampaignChapterResponse.from_model(m)
        fields: dict[str, object] = {f: getattr(base, f) for f in base.__struct_fields__}

        if ChapterInclude.NOTES in includes:
            fields["notes"] = [NoteResponse.from_model(n) for n in m.notes]
        if ChapterInclude.ASSETS in includes:
            fields["assets"] = [S3AssetResponse.from_model(a) for a in m.assets]

        return cls(**fields)  # type: ignore[arg-type]


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
