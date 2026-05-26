"""Test Discord OAuth utility."""

import datetime
from typing import Any

import pytest

from vapi.utils.discord import is_discord_oauth_expired


class TestIsDiscordOauthExpired:
    """Test is_discord_oauth_expired utility."""

    def test_not_expired(self) -> None:
        """Verify non-expired OAuth returns False."""
        expires_at = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)).timestamp()
        oauth = {"expires_at": expires_at}
        result = is_discord_oauth_expired(oauth)
        assert result is False

    def test_expired(self) -> None:
        """Verify expired OAuth returns True."""
        expires_at = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).timestamp()
        oauth = {"expires_at": expires_at}
        result = is_discord_oauth_expired(oauth)
        assert result is True

    @pytest.mark.parametrize(
        "oauth",
        [
            None,
            {"access_token": "abc"},
            {"expires_at": None},
        ],
        ids=["none-oauth", "missing-expires_at", "none-expires_at"],
    )
    def test_returns_false_for_missing_or_null_expiry(self, oauth: dict[str, Any] | None) -> None:
        """Verify None oauth, missing expires_at, and None expires_at all return False."""
        # Given an oauth value with no valid expiry

        # When checking expiry
        result = is_discord_oauth_expired(oauth)

        # Then False is returned
        assert result is False
