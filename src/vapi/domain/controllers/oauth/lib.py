"""OAuth services."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from urllib.parse import quote_plus

from vapi.config.oauth import get_discord_oauth_client
from vapi.db.models.user import DiscordOauth, DiscordProfile, User
from vapi.lib.exceptions import ImproperlyConfiguredError

if TYPE_CHECKING:
    from beanie import PydanticObjectId

from vapi.config import settings


async def get_discord_oauth_url(user_id: PydanticObjectId | str) -> str:
    """Get the URL for the specified user to login via Discord."""
    state = {"user_id": str(user_id)}
    state_json = json.dumps(state)
    return await get_discord_oauth_client().get_authorization_url(
        redirect_uri=settings.oauth.discord_callback_url,
        state=quote_plus(state_json),
    )


async def discord_oauth_token_to_user(user: User, token: dict[str, Any]) -> User:
    """Add the Discord OAuth token to the user."""
    discord_oauth = DiscordOauth(
        access_token=token["access_token"],
        refresh_token=token["refresh_token"],
        expires_in=token["expires_in"],
        expires_at=token["expires_at"],
    )

    user.discord_oauth = discord_oauth
    await user.save()
    return user


async def discord_profile_to_user(user: User) -> User:
    """Add the Discord profile to the user profile."""
    if user.discord_oauth.access_token is None:
        raise ImproperlyConfiguredError(
            detail="Discord OAuth token is not set. User must login again."
        )
    profile = await get_discord_oauth_client().get_profile(user.discord_oauth.access_token)

    discord_profile = DiscordProfile(
        id=profile["id"],
        username=profile["username"],
        global_name=profile["global_name"],
        avatar_id=profile["avatar"],
        discriminator=profile["discriminator"],
        email=profile["email"],
        verified=profile["verified"],
    )
    user.discord_profile = discord_profile
    await user.save()
    return user
