"""OAuth configuration."""

from __future__ import annotations

from functools import lru_cache

from httpx_oauth.clients.discord import DiscordOAuth2

from .base import settings


@lru_cache(maxsize=1)
def get_discord_oauth_client() -> DiscordOAuth2:
    """Return the http_oauth client for Discord."""
    return DiscordOAuth2(
        client_id=settings.oauth.discord_client_id,
        client_secret=settings.oauth.discord_client_secret,
    )
