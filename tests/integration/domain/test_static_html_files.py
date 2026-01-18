"""Test static HTML files."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytestmark = pytest.mark.anyio
if TYPE_CHECKING:
    from httpx import AsyncClient


async def test_robots_txt(client: AsyncClient) -> None:
    """Test robots.txt file."""
    response = await client.get("/robots.txt")
    assert response.status_code == 200
    assert "User-agent: *" in response.text


async def test_404_html(client: AsyncClient) -> None:
    """Test 404.html file."""
    response = await client.get("/nonexistent.html")
    assert response.status_code == 404
    assert "Page not found" in response.text
