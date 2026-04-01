"""Test Discord OAuth utility."""

import datetime

from vapi.utils.discord import is_discord_oauth_expired


class TestDiscordOauthExpired:
    """Test is_discord_oauth_expired utility."""

    def test_not_expired(self) -> None:
        """Verify non-expired OAuth returns False."""
        expires_at = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)).timestamp()
        assert is_discord_oauth_expired({"expires_at": expires_at}) is False

    def test_expired(self) -> None:
        """Verify expired OAuth returns True."""
        expires_at = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).timestamp()
        assert is_discord_oauth_expired({"expires_at": expires_at}) is True

    def test_none(self) -> None:
        """Verify None OAuth returns False."""
        assert is_discord_oauth_expired(None) is False
