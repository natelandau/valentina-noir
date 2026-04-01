"""Discord OAuth utilities."""

import datetime
from typing import Any


def is_discord_oauth_expired(discord_oauth: dict[str, Any] | None) -> bool:
    """Check whether a Discord OAuth token has expired.

    Args:
        discord_oauth: The OAuth data dict containing an optional ``expires_at`` timestamp.

    Returns:
        True if the token is expired, False if valid or data is missing.
    """
    if discord_oauth is None:
        return False

    expires_at = discord_oauth.get("expires_at")
    if expires_at is None:
        return False

    return datetime.datetime.now(datetime.UTC).timestamp() > expires_at
