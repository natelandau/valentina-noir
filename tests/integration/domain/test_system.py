"""Test health."""

import pytest
from httpx import AsyncClient

from vapi import __version__
from vapi.domain import urls

pytestmark = pytest.mark.anyio


async def test_health(client: AsyncClient, token_company_admin: dict[str, str]) -> None:
    """Verify the health endpoint."""
    response = await client.get(urls.System.HEALTH, headers=token_company_admin)
    assert response.status_code == 200

    expected = {
        "database_status": "online",
        "cache_status": "online",
        "version": __version__,
    }

    assert response.json() == expected
