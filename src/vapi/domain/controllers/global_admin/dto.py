"""Developer schemas."""

from __future__ import annotations

from litestar.plugins.pydantic import PydanticDTO

from vapi.db.models import Developer
from vapi.lib.dto import dto_config


class DeveloperCreateDTO(PydanticDTO[Developer]):
    """Developer DTO."""

    config = dto_config(
        exclude={
            "id",
            "api_key_fingerprint",
            "hashed_api_key",
            "key_generated",
            "companies",
            "date_created",
            "date_modified",
        }
    )


class DeveloperPatchDTO(PydanticDTO[Developer]):
    """Update Developer DTO."""

    config = dto_config(
        partial=True,
        exclude={
            "id",
            "api_key_fingerprint",
            "hashed_api_key",
            "key_generated",
            "companies",
            "date_created",
            "date_modified",
        },
    )


class DeveloperReturnDTO(PydanticDTO[Developer]):
    """Developer DTO."""

    config = dto_config(exclude={"api_key_fingerprint", "hashed_api_key"})
