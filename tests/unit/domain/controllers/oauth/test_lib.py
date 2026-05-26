"""Unit tests for the Discord OAuth helper logic."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from vapi.domain.controllers.oauth.lib import (
    discord_profile_to_user,
    is_discord_oauth_expired,
)
from vapi.lib.exceptions import ImproperlyConfiguredError

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


class TestIsDiscordOauthExpired:
    """Tests for is_discord_oauth_expired."""

    @pytest.mark.parametrize(
        ("discord_oauth", "expected"),
        [
            ({"expires_at": datetime.now(UTC).timestamp() - 3600}, True),
            ({"expires_at": datetime.now(UTC).timestamp() + 3600}, False),
            (None, False),
            ({"access_token": "abc"}, False),
        ],
        ids=["expired", "valid", "no_oauth_data", "no_expires_at"],
    )
    def test_reports_expiry_from_expires_at(
        self, discord_oauth: dict | None, expected: bool, mocker: MockerFixture
    ) -> None:
        """Verify expiry is derived from expires_at, treating missing data as not expired."""
        # Given a user with the given Discord OAuth state
        user = mocker.MagicMock(discord_oauth=discord_oauth)

        # When checking expiry
        result = is_discord_oauth_expired(user)

        # Then the result matches the expected expiry
        assert result is expected


class TestDiscordProfileToUser:
    """Tests for the discord_profile_to_user token guard clause."""

    @pytest.mark.parametrize(
        "oauth",
        [None, {}, {"access_token": None}],
        ids=["missing", "empty", "null_access_token"],
    )
    async def test_raises_when_access_token_missing(
        self, oauth: dict | None, mocker: MockerFixture
    ) -> None:
        """Verify a missing or empty access token raises ImproperlyConfiguredError."""
        # Given a user without a usable Discord access token
        user = mocker.MagicMock(discord_oauth=oauth)

        # When loading the profile / Then it raises before any external call
        with pytest.raises(ImproperlyConfiguredError, match="must login again"):
            await discord_profile_to_user(user)
