"""Guards for all controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from beanie import PydanticObjectId
from litestar.serialization import decode_json, encode_json

from vapi.config import settings
from vapi.constants import CompanyPermission, UserRole
from vapi.db.models import Character, Company, User
from vapi.lib.exceptions import ClientError, NotFoundError, PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection
    from litestar.handlers.base import BaseRouteHandler


__all__ = (
    "developer_company_admin_guard",
    "developer_company_owner_guard",
    "developer_company_user_guard",
    "global_admin_guard",
    "user_character_player_or_storyteller_guard",
    "user_storyteller_guard",
)


def global_admin_guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """Guard for admin users."""
    if not connection.user.is_global_admin:
        raise PermissionDeniedError(detail="No rights to access this resource")


async def _is_valid_company(company_id: str) -> Company:
    """Check if a company is valid."""
    if not company_id:
        raise ValidationError(
            detail="Company ID is required",
            invalid_parameters=[
                {"field": "company_id", "message": "Company ID is required"},
            ],
        )

    company = await Company.find_one(
        Company.id == PydanticObjectId(company_id),
        Company.is_archived == False,
    )

    if not company:
        raise NotFoundError(detail=f"Company '{company_id}' not found")
    return company


async def _is_valid_character(character_id: str) -> Character:
    """Check if a character is valid."""
    if not character_id:
        raise ValidationError(
            detail="Character ID is required",
            invalid_parameters=[
                {"field": "character_id", "message": "Character ID is required"},
            ],
        )

    character = await Character.find_one(
        Character.id == PydanticObjectId(character_id),
        Character.is_archived == False,
    )

    if not character:
        raise NotFoundError(detail=f"Character '{character_id}' not found")
    return character


async def _confirm_user_role_from_store(
    *, connection: ASGIConnection, user_roles: list[UserRole]
) -> bool:
    """Confirm a user role from the store.

    Args:
        connection (ASGIConnection): The connection.
        user_roles (list[UserRole]): The user roles.

    Returns:
        bool: True if the user role is in the store, False otherwise.
    """
    user_id = connection.path_params.get("user_id")
    if not user_id:
        raise ValidationError(
            detail="User ID is required",
            invalid_parameters=[
                {"field": "user_id", "message": "User ID is required"},
            ],
        )

    store = connection.app.stores.get(settings.stores.guard_session_key)
    user_from_store = await store.get(f"users:{user_id}", renew_for=settings.stores.ttl)

    if user_from_store:
        data = decode_json(user_from_store)
        user = User(**data)
        user_role = UserRole(user.role)
        if user_role in user_roles:
            return True
        raise PermissionDeniedError

    user = await User.get(user_id)
    await store.set(
        f"users:{user_id}",
        encode_json(user.model_dump(mode="json")),
        expires_in=settings.stores.ttl,
    )
    if user.role not in user_roles:
        raise PermissionDeniedError

    return True


async def user_json_from_cache(connection: ASGIConnection) -> User:
    """Get a user from the cache with fallback to the database."""
    user_id = connection.path_params.get("user_id")
    if not user_id:
        raise ClientError(detail="User ID is required")

    store = connection.app.stores.get(settings.stores.guard_session_key)
    user_from_store = await store.get(f"users:{user_id}", renew_for=settings.stores.ttl)

    if user_from_store:
        data = decode_json(user_from_store)
        return User(**data)

    user = await User.get(user_id)

    if not user:
        raise ClientError(detail=f"User '{user_id}' not found on this server.")

    await store.set(
        f"users:{user_id}",
        encode_json(user.model_dump(mode="json")),
        expires_in=settings.stores.ttl,
    )
    return user


async def developer_company_user_guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """Guard for company users."""
    developer = connection.user
    if developer.is_global_admin:
        return

    company = await _is_valid_company(connection.path_params.get("company_id"))

    for company_permission in developer.companies:
        if company_permission.company_id == company.id:
            return

    raise PermissionDeniedError(detail="No rights to access this resource")


async def developer_company_admin_guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """Guard for company users."""
    developer = connection.user
    if developer.is_global_admin:
        return

    company = await _is_valid_company(connection.path_params.get("company_id"))

    for company_permission in developer.companies:
        if company_permission.company_id == company.id and company_permission.permission in [
            CompanyPermission.ADMIN,
            CompanyPermission.OWNER,
        ]:
            return

    raise PermissionDeniedError(detail="No rights to access this resource")


async def developer_company_owner_guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """Guard for company users."""
    developer = connection.user
    if developer.is_global_admin:
        return

    company = await _is_valid_company(connection.path_params.get("company_id"))

    for company_permission in developer.companies:
        if (
            company_permission.company_id == company.id
            and company_permission.permission == CompanyPermission.OWNER
        ):
            return

    raise PermissionDeniedError(detail="No rights to access this resource")


async def user_storyteller_guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """Guard for campaign storytellers."""
    company_id = connection.path_params.get("company_id")
    user = await user_json_from_cache(connection)
    if (
        UserRole(user.role) not in [UserRole.STORYTELLER, UserRole.ADMIN]
        or str(user.company_id) != company_id
    ):
        raise PermissionDeniedError


async def user_admin_guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """Guard for campaign administrators."""
    user = await user_json_from_cache(connection)
    company_id = connection.path_params.get("company_id")
    if UserRole(user.role) not in [UserRole.ADMIN] or str(user.company_id) != company_id:
        raise PermissionDeniedError


async def user_character_player_or_storyteller_guard(
    connection: ASGIConnection, _: BaseRouteHandler
) -> None:
    """Guard for campaign players or storytellers."""
    character_id = connection.path_params.get("character_id")
    if not character_id:
        raise ClientError(detail="Character ID is required")

    character = await Character.get(character_id)
    if not character or character.is_archived:
        raise NotFoundError(detail=f"Character '{character_id}' not found")

    user = await user_json_from_cache(connection)

    if (
        UserRole(user.role) not in [UserRole.STORYTELLER, UserRole.ADMIN]
        and character.user_player_id != user.id
    ):
        raise PermissionDeniedError
