"""Test Discord OAuth utility."""

import datetime

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

    def test_none_oauth(self) -> None:
        """Verify None OAuth returns False."""
        result = is_discord_oauth_expired(None)
        assert result is False

    def test_missing_expires_at(self) -> None:
        """Verify OAuth without expires_at returns False."""
        oauth = {"access_token": "abc"}
        result = is_discord_oauth_expired(oauth)
        assert result is False

    def test_none_expires_at(self) -> None:
        """Verify OAuth with None expires_at returns False."""
        oauth = {"expires_at": None}
        result = is_discord_oauth_expired(oauth)
        assert result is False
