"""Tortoise-based guards for migrated controllers.

Parallel to guards.py (Beanie-based) during the migration. Once all domains
are migrated (Session 11), delete guards.py and rename this file.

Note: connection.user is still a Beanie Developer (set by auth middleware).
These guards only read .id and .is_global_admin from it.
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
    "pg_developer_company_admin_guard",
    "pg_developer_company_owner_guard",
    "pg_developer_company_user_guard",
    "pg_user_character_player_or_storyteller_guard",
    "pg_user_not_unapproved_guard",
)


async def _pg_check_developer_company_permission(
    connection: "ASGIConnection",
    *,
    allowed_permissions: set[CompanyPermission] | None = None,
) -> None:
    """Verify the developer has the required permission via Tortoise."""
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


async def pg_developer_company_user_guard(
    connection: "ASGIConnection", _: "BaseRouteHandler"
) -> None:
    """Guard requiring any company membership (Tortoise)."""
    await _pg_check_developer_company_permission(connection)


async def pg_developer_company_admin_guard(
    connection: "ASGIConnection", _: "BaseRouteHandler"
) -> None:
    """Guard requiring admin or owner permission (Tortoise)."""
    await _pg_check_developer_company_permission(
        connection,
        allowed_permissions={CompanyPermission.ADMIN, CompanyPermission.OWNER},
    )


async def pg_developer_company_owner_guard(
    connection: "ASGIConnection", _: "BaseRouteHandler"
) -> None:
    """Guard requiring owner permission (Tortoise)."""
    await _pg_check_developer_company_permission(
        connection,
        allowed_permissions={CompanyPermission.OWNER},
    )


async def pg_user_not_unapproved_guard(connection: "ASGIConnection", _: "BaseRouteHandler") -> None:
    """Guard that rejects UNAPPROVED users (Tortoise).

    Extracts user_id from the URL path, queries the Tortoise User table,
    and raises PermissionDeniedError if the user has the UNAPPROVED role.
    """
    user_id_str = connection.path_params.get("user_id")
    if not user_id_str:
        raise PermissionDeniedError(detail="User ID is required")

    try:
        user_uuid = UUID(user_id_str)
    except ValueError as e:
        raise NotFoundError(detail=f"User '{user_id_str}' not found") from e

    user = await User.filter(id=user_uuid, is_archived=False).first()
    if not user:
        raise NotFoundError(detail=f"User '{user_id_str}' not found")

    if user.role == UserRole.UNAPPROVED:
        raise PermissionDeniedError(detail="User has not been approved yet")


async def pg_user_character_player_or_storyteller_guard(
    connection: "ASGIConnection", _: "BaseRouteHandler"
) -> None:
    """Guard requiring character player or storyteller/admin role (Tortoise).

    Extracts character_id from the URL path, queries the Tortoise Character table,
    and raises PermissionDeniedError unless the requesting user is the character's
    player or has STORYTELLER/ADMIN role.
    """
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

    user_id_str = connection.path_params.get("user_id")
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

    if (
        user.role not in {UserRole.STORYTELLER, UserRole.ADMIN}
        and character.user_player_id != user.id  # type: ignore[attr-defined]
    ):
        raise PermissionDeniedError(detail="No rights to access this resource")
