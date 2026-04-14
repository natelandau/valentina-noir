"""Campaign guards."""

import asyncio
from typing import assert_never

from litestar.connection import ASGIConnection
from litestar.handlers.base import BaseRouteHandler

from vapi.constants import ON_BEHALF_OF_HEADER_KEY, PermissionManageCampaign, UserRole
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.lib.exceptions import ClientError, NotFoundError, PermissionDeniedError


async def user_can_manage_campaign(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """Guard to check if the acting user can manage the campaign."""
    company_id = connection.path_params.get("company_id", None)
    if not company_id:
        raise ClientError(detail="Company ID is required")

    user_id = connection.headers.get(ON_BEHALF_OF_HEADER_KEY)
    if not user_id:
        raise ClientError(detail="User ID is required")

    company, user = await asyncio.gather(
        Company.filter(id=company_id, is_archived=False).prefetch_related("settings").first(),
        User.get_or_none(id=user_id),
    )
    if not company:
        raise NotFoundError(detail=f"Company '{company_id}' not found")
    if not user:
        raise ClientError(detail=f"User '{user_id}' not found on this server.")

    match company.settings.permission_manage_campaign:
        case PermissionManageCampaign.UNRESTRICTED:
            connection.scope.setdefault("state", {})["acting_user"] = user
            return

        case PermissionManageCampaign.STORYTELLER:
            if user.role in [UserRole.STORYTELLER, UserRole.ADMIN]:
                connection.scope.setdefault("state", {})["acting_user"] = user
                return
        case _:  # pragma: no cover
            assert_never(company.settings.permission_manage_campaign)

    raise PermissionDeniedError(detail="No rights to access this resource")
