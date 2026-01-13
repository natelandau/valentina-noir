"""Developer schemas."""

from __future__ import annotations

from litestar.plugins.pydantic import PydanticDTO

from vapi.db.models import Developer
from vapi.lib.dto import dto_config


class PatchDTO(PydanticDTO[Developer]):
    """Update Developer DTO."""

    config = dto_config(
        partial=True,
        exclude={
            "id",
            "api_key_fingerprint",
            "date_created",
            "date_modified",
            "hashed_api_key",
            "key_generated",
            "companies",
            "is_global_admin",
        },
    )


class ReturnDTO(PydanticDTO[Developer]):
    """Developer DTO."""

    config = dto_config(exclude={"api_key_fingerprint", "hashed_api_key", "is_global_admin"})
