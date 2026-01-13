"""Assets DTO."""

from __future__ import annotations

from litestar.plugins.pydantic import PydanticDTO

from vapi.db.models import S3Asset
from vapi.lib.dto import dto_config


class AssetResponseDTO(PydanticDTO[S3Asset]):
    """Asset response DTO."""

    config = dto_config(exclude={"s3_key", "s3_bucket"})
