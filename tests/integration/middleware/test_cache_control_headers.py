"""Cache control middleware tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import HTTP_200_OK

from vapi.config import settings
from vapi.domain import urls

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_cached_route_returns_cache_control_header(
    client: AsyncClient,
    build_url: Callable[[str, Any], str],
    token_company_user: dict[str, str],
) -> None:
    """Verify cached route includes private Cache-Control header with max-age."""
    # Given a request to the options endpoint which has cache=600
    url = build_url(urls.Options.LIST)

    # When making a request to the cached endpoint
    response = await client.get(url, headers=token_company_user)

    # Then the response should have cache-control header with correct max-age
    assert response.status_code == HTTP_200_OK
    cache_control = response.headers.get("cache-control")
    assert cache_control is not None
    assert "private" in cache_control
    assert "max-age=600" in cache_control


async def test_cached_route_with_default_ttl(
    client: AsyncClient,
    build_url: Callable[[str, Any], str],
    token_company_user: dict[str, str],
) -> None:
    """Verify route with cache=True uses default TTL from settings."""
    # Given a request to the campaigns list endpoint which has cache=True
    url = build_url(urls.Campaigns.LIST)

    # When making a request to the cached endpoint
    response = await client.get(url, headers=token_company_user)

    # Then the response should have cache-control header with default max-age from settings
    assert response.status_code == HTTP_200_OK
    cache_control = response.headers.get("cache-control")
    assert cache_control is not None
    assert "private" in cache_control
    assert f"max-age={settings.stores.ttl}" in cache_control


async def test_uncached_route_returns_no_cache_header(
    client: AsyncClient,
) -> None:
    """Verify route with cache=False returns no-cache Cache-Control header."""
    # Given a request to the health endpoint which has cache=False

    # When making a request to the uncached endpoint
    response = await client.get(urls.System.HEALTH)

    # Then the response should have cache-control header with no-cache
    assert response.status_code == HTTP_200_OK
    cache_control = response.headers.get("cache-control")
    assert cache_control is not None
    assert cache_control == "no-cache"


async def test_character_blueprint_sections_returns_cache_header(
    client: AsyncClient,
    build_url: Callable[[str, Any], str],
    token_company_user: dict[str, str],
) -> None:
    """Verify character blueprint sections endpoint has cache control header."""
    # Given a request to the character blueprint sections endpoint which has cache=True
    url = build_url(urls.CharacterBlueprints.SECTIONS)

    # When making a request to the cached endpoint
    response = await client.get(url, headers=token_company_user)

    # Then the response should have cache-control header
    assert response.status_code == HTTP_200_OK
    cache_control = response.headers.get("cache-control")
    assert cache_control is not None
    assert "private" in cache_control
    assert f"max-age={settings.stores.ttl}" in cache_control


async def test_campaign_detail_returns_cache_header(
    client: AsyncClient,
    build_url: Callable[[str, Any], str],
    token_company_user: dict[str, str],
) -> None:
    """Verify campaign detail endpoint has cache control header."""
    # Given a request to the campaign detail endpoint which has cache=True
    url = build_url(urls.Campaigns.DETAIL)

    # When making a request to the cached endpoint
    response = await client.get(url, headers=token_company_user)

    # Then the response should have cache-control header
    assert response.status_code == HTTP_200_OK
    cache_control = response.headers.get("cache-control")
    assert cache_control is not None
    assert "private" in cache_control
    assert f"max-age={settings.stores.ttl}" in cache_control
