"""Unit tests for user_active_guard and hardened character guard."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from vapi.constants import UserRole
from vapi.lib.exceptions import PermissionDeniedError
from vapi.lib.guards import user_active_guard, user_character_player_or_storyteller_guard

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


def _mock_connection(mocker: MockerFixture, path_params: dict[str, str]) -> MagicMock:
    """Create a mock ASGIConnection with the given path params."""
    connection = mocker.MagicMock()
    connection.path_params = path_params
    return connection


def _mock_handler(mocker: MockerFixture, opt: dict[str, object] | None = None) -> MagicMock:
    """Create a mock route handler with the given opt dict."""
    handler = mocker.MagicMock()
    handler.opt = opt or {}
    return handler


def _patch_user(mocker: MockerFixture, user: MagicMock | None) -> None:
    """Patch User.filter(...).first() to return the given user."""
    mocker.patch(
        "vapi.lib.guards.User.filter",
        return_value=mocker.MagicMock(first=mocker.AsyncMock(return_value=user)),
    )


async def test_user_active_guard_rejects_deactivated(mocker: MockerFixture) -> None:
    """Verify DEACTIVATED user is rejected with deactivated message."""
    # Given a deactivated user
    user = mocker.MagicMock(role=UserRole.DEACTIVATED)
    _patch_user(mocker, user)
    connection = _mock_connection(mocker, {"user_id": str(uuid4())})

    # When/Then the guard raises
    with pytest.raises(PermissionDeniedError, match="deactivated"):
        await user_active_guard(connection, _mock_handler(mocker))


async def test_user_active_guard_rejects_unapproved(mocker: MockerFixture) -> None:
    """Verify UNAPPROVED user is rejected with not been approved message."""
    # Given an unapproved user
    user = mocker.MagicMock(role=UserRole.UNAPPROVED)
    _patch_user(mocker, user)
    connection = _mock_connection(mocker, {"user_id": str(uuid4())})

    # When/Then the guard raises
    with pytest.raises(PermissionDeniedError, match="not been approved"):
        await user_active_guard(connection, _mock_handler(mocker))


async def test_user_active_guard_allows_unapproved_with_opt_flag(mocker: MockerFixture) -> None:
    """Verify handlers with allow_unapproved_user opt flag can act on UNAPPROVED users."""
    # Given an unapproved user and a handler that opts in to UNAPPROVED access
    user = mocker.MagicMock(role=UserRole.UNAPPROVED)
    _patch_user(mocker, user)
    connection = _mock_connection(mocker, {"user_id": str(uuid4())})
    handler = _mock_handler(mocker, {"allow_unapproved_user": True})

    # When calling the guard / Then no exception
    await user_active_guard(connection, handler)


async def test_user_active_guard_still_rejects_deactivated_with_opt_flag(
    mocker: MockerFixture,
) -> None:
    """Verify allow_unapproved_user opt flag does not bypass the DEACTIVATED check."""
    # Given a deactivated user and a handler that opts in to UNAPPROVED access
    user = mocker.MagicMock(role=UserRole.DEACTIVATED)
    _patch_user(mocker, user)
    connection = _mock_connection(mocker, {"user_id": str(uuid4())})
    handler = _mock_handler(mocker, {"allow_unapproved_user": True})

    # When/Then the guard still rejects
    with pytest.raises(PermissionDeniedError, match="deactivated"):
        await user_active_guard(connection, handler)


async def test_user_active_guard_allows_player(mocker: MockerFixture) -> None:
    """Verify PLAYER user passes the guard."""
    # Given a player user
    user = mocker.MagicMock(role=UserRole.PLAYER)
    _patch_user(mocker, user)
    connection = _mock_connection(mocker, {"user_id": str(uuid4())})

    # When calling the guard / Then no exception
    await user_active_guard(connection, mocker.MagicMock())


async def test_user_active_guard_noop_when_no_user_id_in_path(mocker: MockerFixture) -> None:
    """Verify guard silently returns when user_id is absent from path params."""
    # Given a connection without user_id
    connection = _mock_connection(mocker, {})

    # When calling the guard / Then no exception
    await user_active_guard(connection, mocker.MagicMock())


async def test_character_guard_rejects_deactivated_owner(mocker: MockerFixture) -> None:
    """Verify deactivated owner cannot access their own character."""
    # Given a deactivated user who owns the character
    user_id = uuid4()
    character_id = uuid4()
    user = mocker.MagicMock(role=UserRole.DEACTIVATED, id=user_id)
    character = mocker.MagicMock(user_player_id=user_id)

    mocker.patch(
        "vapi.db.sql_models.character.Character.filter",
        return_value=mocker.MagicMock(first=mocker.AsyncMock(return_value=character)),
    )
    mocker.patch(
        "vapi.lib.guards.User.filter",
        return_value=mocker.MagicMock(first=mocker.AsyncMock(return_value=user)),
    )
    connection = _mock_connection(
        mocker, {"character_id": str(character_id), "user_id": str(user_id)}
    )

    # When/Then the guard raises
    with pytest.raises(PermissionDeniedError, match="No rights"):
        await user_character_player_or_storyteller_guard(connection, mocker.MagicMock())
