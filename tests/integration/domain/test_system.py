"""Test health."""

import pytest
from httpx import AsyncClient

from vapi import __version__
from vapi.domain import urls

pytestmark = pytest.mark.anyio


async def test_health(client: AsyncClient, token_company_admin: dict[str, str]) -> None:
    """Verify the health endpoint returns status, latency, uptime, and version."""
    # Given an authenticated client

    # When requesting the health endpoint
    response = await client.get(urls.System.HEALTH, headers=token_company_admin)

    # Then the response is successful
    assert response.status_code == 200

    # Then all expected fields are present with correct types
    data = response.json()
    assert data["database_status"] == "online"
    assert data["cache_status"] == "online"
    assert data["version"] == __version__
    assert isinstance(data["database_latency_ms"], float)
    assert isinstance(data["cache_latency_ms"], float)
    assert isinstance(data["uptime"], str)
    assert "d" in data["uptime"]
    assert "h" in data["uptime"]


async def test_healthz_needs_no_api_key(client: AsyncClient) -> None:
    """Verify the liveness probe answers without credentials."""
    # Given an unauthenticated client

    # When requesting the liveness endpoint with no headers
    response = await client.get(urls.System.HEALTHZ)

    # Then the response is a bare ok status
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
