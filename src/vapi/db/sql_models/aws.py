"""S3 asset model — file/media storage references."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields

from vapi.constants import AssetParentType, AssetType
from vapi.db.sql_models.base import BaseModel

if TYPE_CHECKING:
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.user import User


class S3Asset(BaseModel):
    """A reference to a file stored in S3."""

    asset_type = fields.CharEnumField(AssetType)
    mime_type = fields.CharField(max_length=100)
    original_filename = fields.CharField(max_length=255)
    parent_type = fields.CharEnumField(AssetParentType)
    parent_id = fields.UUIDField(null=True)
    s3_key = fields.CharField(max_length=500)
    s3_bucket = fields.CharField(max_length=100)
    public_url = fields.TextField()

    company: fields.ForeignKeyRelation[Company] = fields.ForeignKeyField(
        "models.Company", related_name="assets", on_delete=fields.OnDelete.CASCADE
    )
    uploaded_by: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="uploaded_assets",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )

    class Meta:
        """Tortoise ORM meta options."""

        table = "s3_asset"
