"""Test OAuth."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote_plus

import pytest
from httpx_oauth.oauth2 import OAuth2Token
from litestar.status_codes import HTTP_200_OK, HTTP_302_FOUND

from vapi.config.base import settings
from vapi.db.models.user import User

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient
    from pytest_mock import MockerFixture


pytestmark = pytest.mark.anyio

encoded_url = quote_plus(settings.server.url)


@pytest.fixture
async def base_url(base_user) -> str:
    """Create a base URL for the campaign book."""
    return f"/oauth/discord/{base_user.id}/"


async def test_discord_login_url(
    client: AsyncClient,
    base_user: User,
    base_url: str,
    debug: Callable[[Any], None],
    mocker: MockerFixture,
) -> None:
    """Verify Discord login URL generation returns correct authorization URL."""
    # Given: Expected state parameter for the user
    mock_state = f"%257B%2522user_id%2522%253A%2B%2522{base_user.id!s}%2522%257D"

    # Optional: mock client to avoid relying on httpx_oauth URL builder
    mock_client = mocker.AsyncMock()
    expected_url = (
        f"https://discord.com/api/oauth2/authorize?response_type=code"
        f"&client_id=MOCK_CLIENT_ID"
        f"&redirect_uri={encoded_url}%3A8000%2Foauth%2Fdiscord%2Fcallback"
        f"&state={mock_state}&scope=identify+email"
    )
    mock_client.get_authorization_url.return_value = expected_url
    mocker.patch(
        "vapi.domain.controllers.oauth.lib.get_discord_oauth_client",
        return_value=mock_client,
        autospec=True,
    )

    # When
    response = await client.get(f"{base_url}/login/")

    # Then
    assert response.status_code == HTTP_200_OK
    assert response.json()["url"] == expected_url


async def test_discord_login_redirect(
    client: AsyncClient,
    base_user: User,
    base_url: str,
    debug: Callable[[Any], None],
    mocker: MockerFixture,
) -> None:
    """Verify Discord login redirect returns proper redirect response to authorization URL."""
    mock_state = f"%257B%2522user_id%2522%253A%2B%2522{base_user.id!s}%2522%257D"

    mock_client = mocker.AsyncMock()
    expected_url = (
        f"https://discord.com/api/oauth2/authorize?response_type=code"
        f"&client_id=MOCK_CLIENT_ID"
        f"&redirect_uri={settings.server.url}%3A8000%2Foauth%2Fdiscord%2Fcallback"
        f"&state={mock_state}&scope=identify+email"
    )
    mock_client.get_authorization_url.return_value = expected_url
    mocker.patch(
        "vapi.domain.controllers.oauth.lib.get_discord_oauth_client",
        return_value=mock_client,
        autospec=True,
    )

    response = await client.get(f"{base_url}/login/redirect")

    assert response.status_code == HTTP_302_FOUND
    assert response.headers["Location"] == expected_url


async def test_discord_callback(
    client: AsyncClient,
    base_user: User,
    mocker: MockerFixture,
    debug: Callable[[Any], None],
) -> None:
    """Verify Discord OAuth callback processes authorization code and updates user profile."""
    mock_state = f"%7B%22user_id%22%3A+%22{base_user.id!s}%22%7D"
    mock_access_token = "ABCDEFGHIJKLMNOPQRSTUVWXYZ.4sUwuslA4j5ozuDegMyp66jT5ZnjQx"  # noqa: S105
    mock_refresh_token = "ABCDEFGHIJKLMNOPQRSTUVWXYZxUZaQHRABCDEFGsraUP8ZA0w012345s"  # noqa: S105
    mock_token = OAuth2Token(
        {
            "token_type": "Bearer",
            "access_token": mock_access_token,
            "expires_in": 604800,
            "refresh_token": mock_refresh_token,
            "scope": "guilds email identify guilds.join",
            "expires_at": 1761136794,
        }
    )
    mock_profile = {
        "id": "123456789010111213",
        "username": "someusername",
        "avatar": "12345678901012345678901012345678901012",
        "discriminator": "0",
        "public_flags": 0,
        "flags": 0,
        "banner": None,
        "accent_color": None,
        "global_name": "someusername",
        "avatar_decoration_data": None,
        "collectibles": None,
        "display_name_styles": None,
        "banner_color": None,
        "clan": None,
        "primary_guild": None,
        "mfa_enabled": True,
        "locale": "en-US",
        "premium_type": 0,
        "email": "some_email@example.com",
        "verified": True,
    }

    # Given: Mock callback and the OAuth client returned by the getter
    mocker.patch(
        "vapi.server.oauth.OAuth2AuthorizeCallback.__call__",
        new=mocker.AsyncMock(return_value=(mock_token, mock_state)),
    )
    mock_client = mocker.AsyncMock()
    mock_client.get_profile.return_value = mock_profile
    mocker.patch(
        "vapi.domain.controllers.oauth.lib.get_discord_oauth_client",
        return_value=mock_client,
        autospec=True,
    )

    response = await client.get(
        "/oauth/discord/callback",
        params={"code": "1234567890", "state": mock_state},
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["success"] is True
    await base_user.sync()
    assert base_user.discord_oauth.access_token == mock_access_token
    assert base_user.discord_oauth.refresh_token == mock_refresh_token
    assert base_user.discord_oauth.expires_in == 604800
    assert base_user.discord_oauth.expires_at == 1761136794
    assert base_user.discord_profile.id == "123456789010111213"  # gitleaks:allow
    assert base_user.discord_profile.username == "someusername"
    assert base_user.discord_profile.global_name == "someusername"
    assert base_user.discord_profile.avatar_id == "12345678901012345678901012345678901012"
    assert base_user.discord_profile.discriminator == "0"
    assert base_user.discord_profile.email == "some_email@example.com"
    assert base_user.discord_profile.verified is True
    assert (
        base_user.discord_profile.avatar_url
        == "https://cdn.discordapp.com/avatars/123456789010111213/12345678901012345678901012345678901012.png"
    )


async def test_discord_refresh(
    client: AsyncClient,
    base_user: User,
    mocker: MockerFixture,
    debug: Callable[[Any], None],
) -> None:
    """Verify Discord OAuth token refresh updates expired tokens and user profile."""
    mock_access_token = "ABCDEFGHIJKLMNOPQRSTUVWXYZ.4sUwuslA4j5ozuDegMyp66jT5ZnjQx"  # noqa: S105
    mock_refresh_token = "ABCDEFGHIJKLMNOPQRSTUVWXYZxUZaQHRABCDEFGsraUP8ZA0w012345s"  # noqa: S105
    mock_token = OAuth2Token(
        {
            "token_type": "Bearer",
            "access_token": mock_access_token,
            "expires_in": 604800,
            "refresh_token": mock_refresh_token,
            "scope": "guilds email identify guilds.join",
            "expires_at": 1761136794,
        }
    )
    mock_profile = {
        "id": "123456789010111213",
        "username": "a new username",
        "avatar": "12345678901012345678901012345678901012",
        "discriminator": "0",
        "public_flags": 0,
        "flags": 0,
        "banner": None,
        "accent_color": None,
        "global_name": "a new username",
        "avatar_decoration_data": None,
        "collectibles": None,
        "display_name_styles": None,
        "banner_color": None,
        "clan": None,
        "primary_guild": None,
        "mfa_enabled": True,
        "locale": "en-US",
        "premium_type": 0,
        "email": "a_new_email@example.com",
        "verified": True,
    }

    mocker.patch.object(User, "is_discord_oauth_expired", return_value=True)

    mock_client = mocker.AsyncMock()
    mock_client.refresh_token.return_value = mock_token
    mock_client.get_profile.return_value = mock_profile

    # Patch at BOTH usage sites
    mocker.patch(
        "vapi.domain.controllers.oauth.controllers.get_discord_oauth_client",
        return_value=mock_client,
        autospec=True,
    )
    mocker.patch(
        "vapi.domain.controllers.oauth.lib.get_discord_oauth_client",
        return_value=mock_client,
        autospec=True,
    )

    response = await client.get(f"/oauth/discord/{base_user.id}/refresh/")

    assert response.status_code == HTTP_200_OK
    assert response.json()["success"] is True
    await base_user.sync()
    assert base_user.discord_oauth.access_token == mock_access_token
    assert base_user.discord_oauth.refresh_token == mock_refresh_token
    assert base_user.discord_oauth.expires_in == 604800
    assert base_user.discord_oauth.expires_at == 1761136794
