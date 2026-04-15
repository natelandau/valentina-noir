"""Campaign guards."""

import asyncio
from typing import assert_never

from litestar.connection import ASGIConnection
from litestar.handlers.base import BaseRouteHandler

from vapi.constants import PermissionManageCampaign, UserRole
from vapi.db.sql_models.company import Company
from vapi.lib.exceptions import ClientError, NotFoundError, PermissionDeniedError
from vapi.lib.guards import _resolve_acting_user_from_header


async def user_can_manage_campaign(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """Guard to check if the acting user can manage the campaign."""
    company_id = connection.path_params.get("company_id", None)
    if not company_id:
        raise ClientError(detail="Company ID is required")

    company, user = await asyncio.gather(
        Company.filter(id=company_id, is_archived=False).prefetch_related("settings").first(),
        _resolve_acting_user_from_header(connection),
    )
    if not company:
        raise NotFoundError(detail=f"Company '{company_id}' not found")

    match company.settings.permission_manage_campaign:
        case PermissionManageCampaign.UNRESTRICTED:
            return

        case PermissionManageCampaign.STORYTELLER:
            if user.role in [UserRole.STORYTELLER, UserRole.ADMIN]:
                return
        case _:  # pragma: no cover
            assert_never(company.settings.permission_manage_campaign)

    raise PermissionDeniedError(detail="No rights to access this resource")
