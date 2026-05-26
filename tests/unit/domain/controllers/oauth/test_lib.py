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

    def test_returns_true_when_token_expired(self, mocker: MockerFixture) -> None:
        """Verify a token whose expires_at is in the past is reported as expired."""
        # Given a user whose Discord token expired an hour ago
        past = datetime.now(UTC).timestamp() - 3600
        user = mocker.MagicMock(discord_oauth={"expires_at": past})

        # When checking expiry
        result = is_discord_oauth_expired(user)

        # Then the token is expired
        assert result is True

    def test_returns_false_when_token_valid(self, mocker: MockerFixture) -> None:
        """Verify a token whose expires_at is in the future is reported as not expired."""
        # Given a user whose Discord token expires in an hour
        future = datetime.now(UTC).timestamp() + 3600
        user = mocker.MagicMock(discord_oauth={"expires_at": future})

        # When checking expiry
        result = is_discord_oauth_expired(user)

        # Then the token is not expired
        assert result is False

    def test_returns_false_when_no_oauth_data(self, mocker: MockerFixture) -> None:
        """Verify a user with no Discord OAuth data is never considered expired."""
        # Given a user with no Discord OAuth data
        user = mocker.MagicMock(discord_oauth=None)

        # When checking expiry
        result = is_discord_oauth_expired(user)

        # Then the token is not expired
        assert result is False

    def test_returns_false_when_expires_at_absent(self, mocker: MockerFixture) -> None:
        """Verify OAuth data lacking an expires_at value is not considered expired."""
        # Given a user with OAuth data that has no expires_at
        user = mocker.MagicMock(discord_oauth={"access_token": "abc"})

        # When checking expiry
        result = is_discord_oauth_expired(user)

        # Then the token is not expired
        assert result is False


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
