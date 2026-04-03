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

    from vapi.db.sql_models.campaign import Campaign
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.developer import Developer
    from vapi.db.sql_models.user import User

pytestmark = pytest.mark.anyio


async def test_cached_route_returns_cache_control_header(
    client: AsyncClient,
    build_url: Callable[[str, Any], str],
    token_company_user: dict[str, str],
    mirror_company: Company,
    mirror_company_user: Developer,
) -> None:
    """Verify cached route includes private Cache-Control header with max-age."""
    # Given a request to the options endpoint which has cache=600
    url = build_url(urls.Options.LIST, company_id=mirror_company.id)

    # When making a request to the cached endpoint
    response = await client.get(url, headers=token_company_user)

    # Then the response should have cache-control header with correct max-age
    assert response.status_code == HTTP_200_OK
    cache_control = response.headers.get("cache-control")
    assert cache_control is not None
    assert "private" in cache_control
    assert "max-age=600" in cache_control


async def test_cached_blueprint_route_with_default_ttl(
    client: AsyncClient,
    build_url: Callable[[str, Any], str],
    token_company_user: dict[str, str],
    mirror_company: Company,
    mirror_company_user: Developer,
) -> None:
    """Verify blueprint route with cache=True uses default TTL from settings."""
    # Given a request to a cached blueprint endpoint
    url = build_url(urls.CharacterBlueprints.SECTIONS, company_id=mirror_company.id)

    # When making a request to the cached endpoint
    response = await client.get(url, headers=token_company_user)

    # Then the response should have cache-control header with default max-age
    assert response.status_code == HTTP_200_OK
    cache_control = response.headers.get("cache-control")
    assert cache_control is not None
    assert "private" in cache_control
    assert f"max-age={settings.stores.ttl}" in cache_control


@pytest.mark.parametrize(
    "url_name",
    [
        urls.Campaigns.LIST,
        urls.Campaigns.DETAIL,
    ],
)
async def test_cached_campaign_route_with_default_ttl(
    client: AsyncClient,
    build_url: Callable[[str, Any], str],
    token_company_user: dict[str, str],
    mirror_company: Company,
    mirror_company_user: Developer,
    mirror_user: User,
    mirror_campaign: Campaign,
    url_name: str,
) -> None:
    """Verify Tortoise-backed campaign routes with cache=True use default TTL from settings."""
    # Given a request to a Tortoise-backed cached campaign endpoint
    url = build_url(
        url_name,
        company_id=mirror_company.id,
        user_id=mirror_user.id,
        campaign_id=mirror_campaign.id,
    )

    # When making a request to the cached endpoint
    response = await client.get(url, headers=token_company_user)

    # Then the response should have cache-control header with default max-age
    assert response.status_code == HTTP_200_OK
    cache_control = response.headers.get("cache-control")
    assert cache_control is not None
    assert "private" in cache_control
    assert f"max-age={settings.stores.ttl}" in cache_control


async def test_uncached_route_returns_no_cache_header(
    client: AsyncClient,
    token_company_user: dict[str, str],
    mirror_company: Company,
    mirror_company_user: Developer,
) -> None:
    """Verify route with cache=False returns no-cache Cache-Control header."""
    # Given a request to the health endpoint which has cache=False

    # When making a request to the uncached endpoint
    response = await client.get(urls.System.HEALTH, headers=token_company_user)

    # Then the response should have cache-control header with no-cache
    assert response.status_code == HTTP_200_OK
    cache_control = response.headers.get("cache-control")
    assert cache_control is not None
    assert cache_control == "no-cache"
