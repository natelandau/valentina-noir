"""Route guards for Litestar controllers.

Verify developer permissions, user roles, and character ownership before
allowing access to protected endpoints.
"""

import asyncio
from typing import TYPE_CHECKING, Literal, assert_never, overload
from uuid import UUID

from vapi.constants import (
    ON_BEHALF_OF_HEADER_KEY,
    CharacterType,
    CompanyPermission,
    PermissionManageCampaign,
    PermissionManageNPC,
    UserRole,
)
from vapi.db.sql_models import Character, Company, DeveloperCompanyPermission, User
from vapi.db.sql_models.company import CompanySettings
from vapi.lib.exceptions import ClientError, NotFoundError, PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection
    from litestar.handlers.base import BaseRouteHandler
    from tortoise.queryset import QuerySet

__all__ = (
    "INACTIVE_ROLES",
    "STORYTELLER_ROLES",
    "acting_user_sees_storyteller_characters",
    "assert_can_assign_storyteller_type",
    "developer_company_admin_guard",
    "developer_company_owner_guard",
    "developer_company_user_guard",
    "global_admin_guard",
    "npc_management_permitted",
    "parse_acting_user_id",
    "storyteller_character_access_guard",
    "user_active_guard",
    "user_can_edit_character",
    "user_can_manage_campaign",
    "user_character_player_or_storyteller_guard",
    "user_self_or_admin_guard",
    "user_storyteller_guard",
    "visible_characters",
)

# Roles permitted to see and manage storyteller-type characters. Single source of
# truth so the list filter, the access guard, and the create/update check stay in sync.
STORYTELLER_ROLES: frozenset[UserRole] = frozenset({UserRole.STORYTELLER, UserRole.ADMIN})

# Roles that may not act in the company until an admin approves or reactivates them.
INACTIVE_ROLES: frozenset[UserRole] = frozenset({UserRole.UNAPPROVED, UserRole.DEACTIVATED})

_NO_RIGHTS = "No rights to access this resource"


def acting_user_sees_storyteller_characters(connection: "ASGIConnection") -> bool:
    """Return whether the request's acting user may see STORYTELLER-type characters.

    Read the acting user a guard already resolved from the On-Behalf-Of header. A request
    without that header has no end-user role, so it gets the player view.
    """
    state = connection.scope.get("state")
    user = state.get("acting_user") if isinstance(state, dict) else None
    return isinstance(user, User) and user.role in STORYTELLER_ROLES


def visible_characters(
    queryset: "QuerySet[Character]", *, include_storyteller: bool
) -> "QuerySet[Character]":
    """Narrow a character queryset to the rows the caller may see.

    Args:
        queryset: The character queryset to narrow.
        include_storyteller: Whether the caller may see STORYTELLER-type characters.

    Returns:
        The queryset without STORYTELLER-type characters when the caller may not see them.
    """
    if include_storyteller:
        return queryset
    return queryset.exclude(type=CharacterType.STORYTELLER)


def npc_management_permitted(permission: PermissionManageNPC, user: User) -> bool:
    """Return whether the user may manage NPC characters under the company permission.

    Storytellers and admins always may; otherwise the company's
    permission_manage_npc value decides. Used by the character and trait guards and
    the create/convert-to-NPC service check so the rule lives in one place.
    """
    if user.role in STORYTELLER_ROLES:
        return True
    match permission:
        case PermissionManageNPC.UNRESTRICTED:
            return True
        case PermissionManageNPC.STORYTELLER:
            return False
        case _:  # pragma: no cover
            assert_never(permission)


def parse_acting_user_id(value: str) -> UUID:
    """Parse an On-Behalf-Of header value into a user id.

    Guards and the ``acting_user`` provider both read the header, so they share this
    parser to reject a malformed value with the same 400 response.

    Args:
        value: The raw On-Behalf-Of header value.

    Returns:
        The acting user's id.

    Raises:
        ValidationError: If the value is not a valid UUID.
    """
    try:
        return UUID(value)
    except ValueError as e:
        raise ValidationError(
            detail=f"{ON_BEHALF_OF_HEADER_KEY} header must be a valid UUID",
            invalid_parameters=[
                {"field": ON_BEHALF_OF_HEADER_KEY, "message": "Must be a valid ID."},
            ],
        ) from e


def _path_uuid(connection: "ASGIConnection", key: str, label: str) -> UUID | None:
    """Parse an id path param so queries never filter on a raw string.

    Routes declare id params as ``str``, so a malformed id reaches the guards unparsed.

    Args:
        connection: The ASGI connection.
        key: The path param name, such as ``company_id``.
        label: The resource name for the not-found message, such as ``Company``.

    Returns:
        The parsed id, or None when the route has no such param.

    Raises:
        NotFoundError: If the param is not a valid UUID.
    """
    value = connection.path_params.get(key)
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError as e:
        raise NotFoundError(detail=f"{label} '{value}' not found") from e


def _company_scope(connection: "ASGIConnection") -> dict[str, UUID]:
    """Return a filter that scopes a query to the path company, or no filter without one."""
    company_uuid = _path_uuid(connection, "company_id", "Company")
    return {} if company_uuid is None else {"company_id": company_uuid}


@overload
async def _resolve_acting_user_from_header(
    connection: "ASGIConnection", *, required: Literal[True] = True
) -> User: ...


@overload
async def _resolve_acting_user_from_header(
    connection: "ASGIConnection", *, required: Literal[False]
) -> User | None: ...


async def _resolve_acting_user_from_header(
    connection: "ASGIConnection",
    *,
    required: bool = True,
) -> User | None:
    """Read the On-Behalf-Of header, parse the UUID, and load the user.

    Stashes the loaded user on ``connection.scope["state"]["acting_user"]`` for
    downstream DI providers to reuse without a duplicate query.

    Args:
        connection: The ASGI connection.
        required: If True, raise PermissionDeniedError when the header is missing, so
            the caller always gets a User. If False, return None silently.

    Returns:
        The loaded User, or None when the header is absent and required=False.

    Raises:
        PermissionDeniedError: If the header is required but missing.
        NotFoundError: If the user or the path company doesn't exist.
    """
    # Return the stashed user if a prior guard already resolved it
    state = connection.scope.get("state")
    if isinstance(state, dict):
        stashed = state.get("acting_user")
        if isinstance(stashed, User):
            return stashed

    user_id_str = connection.headers.get(ON_BEHALF_OF_HEADER_KEY)
    if not user_id_str:
        if required:
            raise PermissionDeniedError(detail="On-Behalf-Of header is required")
        return None

    user_uuid = parse_acting_user_id(user_id_str)
    user = await User.filter(id=user_uuid, is_archived=False, **_company_scope(connection)).first()
    if not user:
        raise NotFoundError(detail=f"User '{user_id_str}' not found")

    connection.scope.setdefault("state", {})["acting_user"] = user
    return user


async def _check_developer_company_permission(
    connection: "ASGIConnection",
    *,
    allowed_permissions: set[CompanyPermission] | None = None,
) -> None:
    """Verify the developer has the required permission for the authenticated developer."""
    developer = connection.user
    if developer.is_global_admin:
        return

    # A malformed company id gets the same 403 as a company the developer cannot access
    try:
        company_uuid = _path_uuid(connection, "company_id", "Company")
    except NotFoundError:
        company_uuid = None
    if company_uuid is None:
        raise PermissionDeniedError(detail=_NO_RIGHTS)

    # Skip separate company existence check — the DI provider already validates
    # the company, and the permission query implicitly proves it exists
    perm = (
        await DeveloperCompanyPermission.filter(
            developer_id=developer.id,
            company_id=company_uuid,
            company__is_archived=False,
        )
        .exclude(permission=CompanyPermission.REVOKE)
        .first()
    )

    if perm and (allowed_permissions is None or perm.permission in allowed_permissions):
        return

    raise PermissionDeniedError(detail=_NO_RIGHTS)


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
        raise PermissionDeniedError(detail=_NO_RIGHTS)


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
    user = await _resolve_acting_user_from_header(connection, required=False)
    if user is None:
        return

    allow_unapproved = bool(route_handler.opt.get("allow_unapproved_user", False))

    if user.role == UserRole.UNAPPROVED and not allow_unapproved:
        raise PermissionDeniedError(detail="User has not been approved yet")
    if user.role == UserRole.DEACTIVATED:
        raise PermissionDeniedError(detail="User account is deactivated")


async def user_storyteller_guard(connection: "ASGIConnection", _: "BaseRouteHandler") -> None:
    """Guard that requires STORYTELLER or ADMIN role.

    Read the acting user from the On-Behalf-Of header and raise PermissionDeniedError
    if the user does not have STORYTELLER or ADMIN role.
    """
    user = await _resolve_acting_user_from_header(connection)

    if user.role not in STORYTELLER_ROLES:
        raise PermissionDeniedError(detail="User must be a storyteller or admin")


async def user_self_or_admin_guard(connection: "ASGIConnection", _: "BaseRouteHandler") -> None:
    """Guard requiring the acting user to be the target user or an admin.

    Read ``user_id`` from the path and the acting user from the On-Behalf-Of header.
    Allow the request when the acting user is that target user or has the ADMIN role;
    otherwise deny. Used on self-service endpoints (e.g. avatar management) where a
    user may manage only their own resource unless they are an admin.
    """
    target_uuid = _path_uuid(connection, "user_id", "User")
    if target_uuid is None:
        raise ValidationError(
            detail="User ID is required",
            invalid_parameters=[{"field": "user_id", "message": "User ID is required"}],
        )

    user = await _resolve_acting_user_from_header(connection)

    if user.role == UserRole.ADMIN or user.id == target_uuid:
        return

    raise PermissionDeniedError(detail=_NO_RIGHTS)


async def _load_character_and_acting_user(
    connection: "ASGIConnection", character_uuid: UUID
) -> tuple[Character, User]:
    """Load the path's non-archived character and the required acting user in parallel.

    The character is scoped to the path company when the route has one, so a character
    from another company is not-found (matching provide_character_by_id_and_company)
    instead of leaking its existence via a 403.

    Raises:
        NotFoundError: If the character does not exist.
    """
    character, user = await asyncio.gather(
        Character.filter(
            id=character_uuid, is_archived=False, **_company_scope(connection)
        ).first(),
        _resolve_acting_user_from_header(connection),
    )
    if not character:
        raise NotFoundError(
            detail=f"Character '{connection.path_params['character_id']}' not found"
        )
    return character, user


async def user_character_player_or_storyteller_guard(
    connection: "ASGIConnection", _: "BaseRouteHandler"
) -> None:
    """Guard requiring character player or storyteller/admin role.

    Read the acting user from the On-Behalf-Of header and character_id from
    path params. Raise PermissionDeniedError unless ``user_can_edit_character``
    allows the acting user to edit the character.
    """
    character_uuid = _path_uuid(connection, "character_id", "Character")
    if character_uuid is None:
        raise ValidationError(
            detail="Character ID is required",
            invalid_parameters=[
                {"field": "character_id", "message": "Character ID is required"},
            ],
        )

    character, user = await _load_character_and_acting_user(connection, character_uuid)
    if not await user_can_edit_character(character=character, user=user):
        raise PermissionDeniedError(detail=_NO_RIGHTS)


async def user_can_edit_character(*, character: Character, user: User) -> bool:
    """Return whether the user may edit the character as its player or as a storyteller.

    Shared by the route guard and by saves that re-check access against the locked row,
    because a storyteller can archive, reassign, or convert the character mid-request.

    Args:
        character: The character to edit, as currently stored.
        user: The acting user.

    Returns:
        True when the user is an active storyteller or admin, the character's player, or
        permitted to manage the company's NPCs when the character is an NPC.
    """
    if user.role in INACTIVE_ROLES:
        return False
    if user.role in STORYTELLER_ROLES:
        return True

    # NPCs are ownerless, so the company's permission_manage_npc setting decides
    if character.type == CharacterType.NPC:
        settings = await CompanySettings.filter(company_id=character.company_id).first()  # ty:ignore[missing-attribute]
        return settings is not None and npc_management_permitted(
            settings.permission_manage_npc, user
        )

    return character.user_player_id == user.id  # ty:ignore[missing-attribute]


async def user_can_manage_campaign(connection: "ASGIConnection", _: "BaseRouteHandler") -> None:
    """Guard to check if the acting user can manage the campaign.

    Require the On-Behalf-Of header (a request without it gets 403), then check the
    company's ``permission_manage_campaign`` setting and verify the acting user's role
    satisfies it. Used on mutating campaign, book, chapter, and related asset endpoints.
    """
    company_uuid = _path_uuid(connection, "company_id", "Company")
    if company_uuid is None:
        raise ClientError(detail="Company ID is required")

    company, user = await asyncio.gather(
        Company.filter(id=company_uuid, is_archived=False).prefetch_related("settings").first(),
        _resolve_acting_user_from_header(connection),
    )
    if not company:
        raise NotFoundError(detail=f"Company '{company_uuid}' not found")

    if user.role in INACTIVE_ROLES:
        raise PermissionDeniedError(detail=_NO_RIGHTS)

    match company.settings.permission_manage_campaign:
        case PermissionManageCampaign.UNRESTRICTED:
            return

        case PermissionManageCampaign.STORYTELLER:
            if user.role in STORYTELLER_ROLES:
                return
        case _:  # pragma: no cover
            assert_never(company.settings.permission_manage_campaign)

    raise PermissionDeniedError(detail=_NO_RIGHTS)


async def storyteller_character_access_guard(
    connection: "ASGIConnection", _: "BaseRouteHandler"
) -> None:
    """Hide STORYTELLER-type characters from non-storyteller users.

    Read ``character_id`` from the path. When present, require the On-Behalf-Of header
    (a request without it gets 403), load the character and the acting user, and raise
    PermissionDeniedError if the character is a STORYTELLER type while the acting user
    is neither a storyteller nor an admin. Return early when no ``character_id`` is
    present so the guard can sit at controller scope alongside list and create routes
    that share the controller.
    """
    character_uuid = _path_uuid(connection, "character_id", "Character")
    if character_uuid is None:
        return

    character, user = await _load_character_and_acting_user(connection, character_uuid)
    hidden = character.type == CharacterType.STORYTELLER and user.role not in STORYTELLER_ROLES
    if user.role in INACTIVE_ROLES or hidden:
        raise PermissionDeniedError(detail=_NO_RIGHTS)


def assert_can_assign_storyteller_type(user: User, requested_type: CharacterType) -> None:
    """Reject assigning the STORYTELLER character type to non-storyteller users.

    Call from create and update handlers where the requested character type comes
    from the request body and therefore cannot be checked by a connection guard.
    """
    if requested_type == CharacterType.STORYTELLER and user.role not in STORYTELLER_ROLES:
        raise PermissionDeniedError(detail=_NO_RIGHTS)
