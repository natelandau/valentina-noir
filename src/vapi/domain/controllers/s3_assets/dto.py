"""S3 Assets DTO."""

from datetime import datetime
from uuid import UUID

import msgspec

from vapi.db.sql_models.aws import S3Asset


class S3AssetResponse(msgspec.Struct):
    """Response body for an S3 asset."""

    id: UUID
    date_created: datetime
    date_modified: datetime
    asset_type: str
    mime_type: str
    original_filename: str
    public_url: str
    company_id: UUID
    uploaded_by_id: UUID | None
    character_id: UUID | None
    campaign_id: UUID | None
    book_id: UUID | None
    chapter_id: UUID | None
    user_parent_id: UUID | None

    @classmethod
    def from_model(cls, m: S3Asset) -> "S3AssetResponse":
        """Convert a Tortoise S3Asset to a response Struct."""
        return cls(
            id=m.id,
            date_created=m.date_created,
            date_modified=m.date_modified,
            asset_type=m.asset_type.value if hasattr(m.asset_type, "value") else m.asset_type,
            mime_type=m.mime_type,
            original_filename=m.original_filename,
            public_url=m.public_url,
            company_id=m.company_id,  # type: ignore[attr-defined]
            uploaded_by_id=m.uploaded_by_id,  # type: ignore[attr-defined]
            character_id=m.character_id,  # type: ignore[attr-defined]
            campaign_id=m.campaign_id,  # type: ignore[attr-defined]
            book_id=m.book_id,  # type: ignore[attr-defined]
            chapter_id=m.chapter_id,  # type: ignore[attr-defined]
            user_parent_id=m.user_parent_id,  # type: ignore[attr-defined]
        )
