"""Test health."""

import pytest
from httpx import AsyncClient

from vapi import __version__
from vapi.constants import URL_ROOT_PATH

pytestmark = pytest.mark.anyio


async def test_health(client: AsyncClient) -> None:
    """Verify the health endpoint."""
    response = await client.get(URL_ROOT_PATH + "/health")
    assert response.status_code == 200

    expected = {
        "database_status": "online",
        "cache_status": "online",
        "version": __version__,
    }

    assert response.json() == expected
