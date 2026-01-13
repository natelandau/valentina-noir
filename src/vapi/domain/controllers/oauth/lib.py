"""OAuth services."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import quote_plus

from vapi.config.oauth import get_discord_oauth_client
from vapi.db.models.user import DiscordOauth, DiscordProfile, User
from vapi.lib.exceptions import ImproperlyConfiguredError

if TYPE_CHECKING:
    from beanie import PydanticObjectId

from vapi.config import settings

DISCORD_IMAGE_BASE_URL: Final[str] = "https://cdn.discordapp.com/"
DISCORD_EMBED_BASE_BASE_URL: Final[str] = "https://cdn.discordapp.com/"
DISCORD_IMAGE_FORMAT: Final[str] = "png"
DISCORD_ANIMATED_IMAGE_FORMAT: Final[str] = "gif"
DISCORD_USER_AVATAR_BASE_URL: Final[str] = (
    DISCORD_IMAGE_BASE_URL + "avatars/{user_id}/{avatar_hash}.{format}"
)
DISCORD_DEFAULT_USER_AVATAR_BASE_URL: Final[str] = (
    DISCORD_EMBED_BASE_BASE_URL + "embed/avatars/{modulo5}.png"
)


async def get_discord_oauth_url(user_id: PydanticObjectId | str) -> str:
    """Get the URL for the specified user to login via Discord."""
    state = {"user_id": str(user_id)}
    state_json = json.dumps(state)
    return await get_discord_oauth_client().get_authorization_url(
        redirect_uri=settings.oauth.discord_callback_url,
        state=quote_plus(state_json),
    )


def _get_discord_avatar_url(
    avatar_hash: str, discord_user_id: int, discriminator: str
) -> str | None:
    """Return the URL of the user's avatar.

    Args:
        avatar_hash (str): The hash of the avatar.
        discord_user_id (int): The ID of the discord user.
        discriminator (str): The discriminator of the discord user.

    Returns:
        str | None: The URL of the avatar.
    """

    def _is_avatar_animated(avatar_hash: str) -> bool:
        """A boolean representing if avatar of user is animated. Meaning user has GIF avatar.

        Args:
            avatar_hash (str): The hash of the avatar.

        Returns:
            bool: True if the avatar is animated, False otherwise.
        """
        try:
            return avatar_hash.startswith("a_")
        except AttributeError:
            return False

    def _default_avatar_url(discriminator: str) -> str:
        """Return the default avatar URL as when user doesn't has any avatar set.

        Args:
            discriminator (str): The discriminator of the discord user.

        Returns:
            str: The default avatar URL.
        """
        return DISCORD_DEFAULT_USER_AVATAR_BASE_URL.format(modulo5=int(discriminator) % 5)

    if not avatar_hash:
        return _default_avatar_url(discriminator)
    image_format = (
        DISCORD_ANIMATED_IMAGE_FORMAT if _is_avatar_animated(avatar_hash) else DISCORD_IMAGE_FORMAT
    )
    return DISCORD_USER_AVATAR_BASE_URL.format(
        user_id=discord_user_id, avatar_hash=avatar_hash, format=image_format
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

    avatar_url = _get_discord_avatar_url(
        avatar_hash=profile["avatar"],
        discord_user_id=profile["id"],
        discriminator=profile["discriminator"],
    )

    discord_profile = DiscordProfile(
        id=profile["id"],
        username=profile["username"],
        global_name=profile["global_name"],
        avatar_id=profile["avatar"],
        avatar_url=avatar_url,
        discriminator=profile["discriminator"],
        email=profile["email"],
        verified=profile["verified"],
    )
    user.discord_profile = discord_profile
    await user.save()
    return user
