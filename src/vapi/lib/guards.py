"""Route guards for Litestar controllers.

Verify developer permissions, user roles, and character ownership before
allowing access to protected endpoints.
"""

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from vapi.constants import CompanyPermission, UserRole
from vapi.db.sql_models.developer import DeveloperCompanyPermission
from vapi.db.sql_models.user import User
from vapi.lib.exceptions import NotFoundError, PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection
    from litestar.handlers.base import BaseRouteHandler

__all__ = (
    "developer_company_admin_guard",
    "developer_company_owner_guard",
    "developer_company_user_guard",
    "global_admin_guard",
    "user_active_guard",
    "user_character_player_or_storyteller_guard",
    "user_storyteller_guard",
)


async def _check_developer_company_permission(
    connection: "ASGIConnection",
    *,
    allowed_permissions: set[CompanyPermission] | None = None,
) -> None:
    """Verify the developer has the required permission for the authenticated developer."""
    developer = connection.user
    if developer.is_global_admin:
        return

    company_id_str = connection.path_params.get("company_id")

    try:
        company_uuid = UUID(company_id_str)
        developer_uuid = UUID(str(developer.id))
    except (ValueError, TypeError) as e:
        raise PermissionDeniedError(detail="No rights to access this resource") from e

    # Skip separate company existence check — the DI provider already validates
    # the company, and the permission query implicitly proves it exists
    perm = await DeveloperCompanyPermission.filter(
        developer_id=developer_uuid,
        company_id=company_uuid,
        company__is_archived=False,
    ).first()

    if perm and (allowed_permissions is None or perm.permission in allowed_permissions):
        return

    raise PermissionDeniedError(detail="No rights to access this resource")


async def developer_company_user_guard(connection: "ASGIConnection", _: "BaseRouteHandler") -> None:
    """Guard requiring any company membership."""
    await _check_developer_company_permission(connection)


async def developer_company_admin_guard(
    connection: "ASGIConnection", _: "BaseRouteHandler"
) -> None:
    """Guard requiring admin or owner permission."""
    await _check_developer_company_permission(
        connection,
        allowed_permissions={CompanyPermission.ADMIN, CompanyPermission.OWNER},
    )


async def developer_company_owner_guard(
    connection: "ASGIConnection", _: "BaseRouteHandler"
) -> None:
    """Guard requiring owner permission."""
    await _check_developer_company_permission(
        connection,
        allowed_permissions={CompanyPermission.OWNER},
    )


async def global_admin_guard(connection: "ASGIConnection", _: "BaseRouteHandler") -> None:
    """Verify the authenticated developer is a global admin."""
    if not connection.user.is_global_admin:
        raise PermissionDeniedError(detail="No rights to access this resource")


async def user_active_guard(
    connection: "ASGIConnection", route_handler: "BaseRouteHandler"
) -> None:
    """Guard that rejects UNAPPROVED and DEACTIVATED users.

    Read the acting user from the On-Behalf-Of header and reject the request
    if the user is unapproved or deactivated. Silently return when no header
    is present, so the guard can be safely attached at controller scope for
    endpoints that don't carry an acting user.

    Handlers that intentionally operate on UNAPPROVED users (e.g. approve, deny)
    can opt out of the UNAPPROVED check by setting ``opt={"allow_unapproved_user": True}``
    on the route decorator. The DEACTIVATED check is always enforced.
    """
    from vapi.constants import ON_BEHALF_OF_HEADER_KEY

    user_id_str = connection.headers.get(ON_BEHALF_OF_HEADER_KEY)
    if not user_id_str:
        return

    allow_unapproved = bool(route_handler.opt.get("allow_unapproved_user", False))

    try:
        user_uuid = UUID(user_id_str)
    except ValueError as e:
        raise NotFoundError(detail=f"User '{user_id_str}' not found") from e

    user = await User.filter(id=user_uuid, is_archived=False).first()
    if not user:
        raise NotFoundError(detail=f"User '{user_id_str}' not found")

    if user.role == UserRole.UNAPPROVED and not allow_unapproved:
        raise PermissionDeniedError(detail="User has not been approved yet")
    if user.role == UserRole.DEACTIVATED:
        raise PermissionDeniedError(detail="User account is deactivated")

    connection.scope.setdefault("state", {})["acting_user"] = user


async def user_storyteller_guard(connection: "ASGIConnection", _: "BaseRouteHandler") -> None:
    """Guard that requires STORYTELLER or ADMIN role.

    Read the acting user from the On-Behalf-Of header, query the Tortoise
    User table, and raise PermissionDeniedError if the user does not have
    STORYTELLER or ADMIN role.
    """
    from vapi.constants import ON_BEHALF_OF_HEADER_KEY

    user_id_str = connection.headers.get(ON_BEHALF_OF_HEADER_KEY)
    if not user_id_str:
        raise PermissionDeniedError(detail="User ID is required")

    try:
        user_uuid = UUID(user_id_str)
    except ValueError as e:
        raise NotFoundError(detail=f"User '{user_id_str}' not found") from e

    user = await User.filter(id=user_uuid, is_archived=False).first()
    if not user:
        raise NotFoundError(detail=f"User '{user_id_str}' not found")

    if user.role not in {UserRole.STORYTELLER, UserRole.ADMIN}:
        raise PermissionDeniedError(detail="User must be a storyteller or admin")

    connection.scope.setdefault("state", {})["acting_user"] = user


async def user_character_player_or_storyteller_guard(
    connection: "ASGIConnection", _: "BaseRouteHandler"
) -> None:
    """Guard requiring character player or storyteller/admin role.

    Read the acting user from the On-Behalf-Of header and character_id from
    path params. Raise PermissionDeniedError unless the acting user is the
    character's player or has STORYTELLER/ADMIN role.
    """
    from vapi.constants import ON_BEHALF_OF_HEADER_KEY
    from vapi.db.sql_models.character import Character

    character_id_str = connection.path_params.get("character_id")
    if not character_id_str:
        raise ValidationError(
            detail="Character ID is required",
            invalid_parameters=[
                {"field": "character_id", "message": "Character ID is required"},
            ],
        )

    try:
        character_uuid = UUID(character_id_str)
    except ValueError as e:
        raise NotFoundError(detail=f"Character '{character_id_str}' not found") from e

    user_id_str = connection.headers.get(ON_BEHALF_OF_HEADER_KEY)
    if not user_id_str:
        raise PermissionDeniedError(detail="User ID is required")

    try:
        user_uuid = UUID(user_id_str)
    except ValueError as e:
        raise NotFoundError(detail=f"User '{user_id_str}' not found") from e

    # Fetch character and user in parallel since they are independent lookups
    character, user = await asyncio.gather(
        Character.filter(id=character_uuid, is_archived=False).first(),
        User.filter(id=user_uuid, is_archived=False).first(),
    )

    if not character:
        raise NotFoundError(detail=f"Character '{character_id_str}' not found")
    if not user:
        raise NotFoundError(detail=f"User '{user_id_str}' not found")

    if user.role in {UserRole.UNAPPROVED, UserRole.DEACTIVATED}:
        raise PermissionDeniedError(detail="No rights to access this resource")

    if (
        user.role not in {UserRole.STORYTELLER, UserRole.ADMIN}
        and character.user_player_id != user.id  # type: ignore[attr-defined]
    ):
        raise PermissionDeniedError(detail="No rights to access this resource")

    connection.scope.setdefault("state", {})["acting_user"] = user
