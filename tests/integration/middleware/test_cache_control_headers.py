"""Cache control middleware tests."""

from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient
from litestar.status_codes import HTTP_200_OK

from vapi.config import settings
from vapi.db.sql_models.campaign import Campaign as PgCampaign
from vapi.db.sql_models.company import Company as PgCompany
from vapi.db.sql_models.developer import Developer as PgDeveloper
from vapi.db.sql_models.user import User as PgUser
from vapi.domain import urls

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


async def test_cached_beanie_route_with_default_ttl(
    client: AsyncClient,
    build_url: Callable[[str, Any], str],
    token_company_user: dict[str, str],
) -> None:
    """Verify Beanie-backed route with cache=True uses default TTL from settings."""
    # Given a request to a Beanie-backed cached endpoint
    url = build_url(urls.CharacterBlueprints.SECTIONS)

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
    pg_mirror_company: PgCompany,
    pg_mirror_company_user: PgDeveloper,
    pg_mirror_user: PgUser,
    pg_mirror_campaign: PgCampaign,
    neutralize_after_response_hook: None,
    url_name: str,
) -> None:
    """Verify Tortoise-backed campaign routes with cache=True use default TTL from settings."""
    # Given a request to a Tortoise-backed cached campaign endpoint
    url = build_url(
        url_name,
        company_id=pg_mirror_company.id,
        user_id=pg_mirror_user.id,
        campaign_id=pg_mirror_campaign.id,
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
