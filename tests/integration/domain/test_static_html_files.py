"""Test static file routing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.constants import DOCS_URL
from vapi.domain.controllers.static.static_files import PUBLIC_DIR

pytestmark = pytest.mark.anyio
if TYPE_CHECKING:
    from httpx import AsyncClient


async def test_homepage_redirects_to_docs(client: AsyncClient) -> None:
    """Verify the root path issues a temporary redirect to the documentation site."""
    # Given a running app
    # When the root path is requested
    response = await client.get("/")

    # Then it returns a 302 redirect to the docs site
    assert response.status_code == 302
    assert response.headers["location"] == DOCS_URL


async def test_robots_txt_served(client: AsyncClient) -> None:
    """Verify robots.txt is served as text."""
    # Given a running app
    # When robots.txt is requested
    response = await client.get("/robots.txt")

    # Then it returns the robots policy
    assert response.status_code == 200
    assert "User-agent: *" in response.text


async def test_static_router_serves_file(client: AsyncClient) -> None:
    """Verify files in the public directory are served verbatim under /static."""
    # Given a file in the public static directory
    asset = PUBLIC_DIR / "test-marker.txt"
    asset.write_text("static asset body", encoding="utf-8")

    # When it is requested under /static
    try:
        response = await client.get("/static/test-marker.txt")
    finally:
        asset.unlink()

    # Then it is served verbatim
    assert response.status_code == 200
    assert response.text == "static asset body"


async def test_unknown_path_returns_json_404(client: AsyncClient) -> None:
    """Verify an unknown path returns a JSON 404 rather than an HTML page."""
    # Given a running app
    # When a path matching no route is requested
    response = await client.get("/wp-login.php")

    # Then it returns a JSON problem-detail 404 with no HTML body
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "Page not found" not in response.text


async def test_missing_asset_returns_json_404(client: AsyncClient) -> None:
    """Verify a missing file under /static returns a JSON 404."""
    # Given a running app
    # When a nonexistent asset is requested
    response = await client.get("/static/does-not-exist.txt")

    # Then it returns a JSON problem-detail 404
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
