"""AWS file model."""

from typing import ClassVar

from beanie import PydanticObjectId
from pydantic import Field

from vapi.constants import S3AssetParentType, S3AssetType
from vapi.db.models.base import BaseDocument


class S3Asset(BaseDocument):
    """S3 asset model."""

    asset_type: S3AssetType
    mime_type: str
    original_filename: str

    parent_type: S3AssetParentType = Field(default=S3AssetParentType.UNKNOWN)
    parent_id: PydanticObjectId | None = None
    company_id: PydanticObjectId
    uploaded_by: PydanticObjectId

    s3_key: str
    s3_bucket: str
    public_url: str

    class Settings:
        """Settings for the Character model."""

        indexes: ClassVar[list[str]] = [
            "company_id",
            "parent_id",
            "uploaded_by",
            "asset_type",
        ]
