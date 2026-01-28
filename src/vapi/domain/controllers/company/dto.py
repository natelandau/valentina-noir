"""Company schemas."""

from typing import Any

from beanie import PydanticObjectId
from litestar.plugins.pydantic import PydanticDTO
from pydantic import BaseModel

from vapi.constants import CompanyPermission
from vapi.db.models import Company
from vapi.lib.dto import dto_config


class PostCompanyDTO(PydanticDTO[Company]):
    """Company post DTO."""

    config = dto_config(exclude={"id", "date_created", "date_modified", "user_ids"})


class PatchCompanyDTO(PydanticDTO[Company]):
    """Company patch DTO."""

    config = dto_config(partial=True, exclude={"id", "date_created", "date_modified", "user_ids"})


class CompanyDTO(PydanticDTO[Company]):
    """Company return DTO."""

    config = dto_config()


class CompanyPermissionsDTO(BaseModel):
    """Company permissions DTO."""

    permission: CompanyPermission
    developer_id: PydanticObjectId


class NewCompanyResponseDTO(BaseModel):
    """New company response DTO."""

    company: dict[str, Any]
    admin_user: dict[str, Any]
