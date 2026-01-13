"""Test user."""

from __future__ import annotations

import datetime

import pytest

from vapi.db.models.user import DiscordOauth, User

pytestmark = pytest.mark.anyio


async def test_user_not_expired(base_user: User) -> None:
    """Test the user computed fields."""
    base_user.discord_oauth = DiscordOauth()
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)

    base_user.discord_oauth.expires_at = expires_at.timestamp()
    assert base_user.discord_oauth.expires_at is not None
    assert base_user.is_discord_oauth_expired() is False


async def test_user_expired(base_user: User) -> None:
    """Test the user computed fields."""
    base_user.discord_oauth = DiscordOauth()
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=-1)

    base_user.discord_oauth.expires_at = expires_at.timestamp()
    assert base_user.discord_oauth.expires_at is not None
    assert base_user.is_discord_oauth_expired() is True


async def test_user_expired_none(base_user: User) -> None:
    """Test the user computed fields."""
    base_user.discord_oauth = DiscordOauth()
    assert base_user.is_discord_oauth_expired() is False
