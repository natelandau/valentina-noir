"""Campaign guards."""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from vapi.constants import PermissionManageCampaign, UserRole
from vapi.db.models import Company
from vapi.lib.exceptions import ClientError, NotFoundError, PermissionDeniedError
from vapi.lib.guards import user_json_from_store

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection
    from litestar.handlers.base import BaseRouteHandler


async def user_can_manage_campaign(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """Guard to check if the user can manage the campaign."""
    company_id = connection.path_params.get("company_id", None)
    if not company_id:
        raise ClientError(detail="Company ID is required")
    company = await Company.get(company_id)
    if not company or company.is_archived:
        raise NotFoundError(detail=f"Company '{company_id}' not found")

    user = await user_json_from_store(connection)

    match company.settings.permission_manage_campaign:
        case PermissionManageCampaign.UNRESTRICTED:
            return

        case PermissionManageCampaign.STORYTELLER:
            if user.role in [UserRole.STORYTELLER, UserRole.ADMIN]:
                return
        case _:
            assert_never(company.settings.permission_manage_campaign)

    raise PermissionDeniedError(detail="No rights to access this resource")
