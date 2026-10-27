"""Test the router that serves public static files."""

from pathlib import Path

import pytest
from litestar import Litestar
from litestar.testing import AsyncTestClient

from vapi.domain.controllers.static.static_files import create_public_files_router

pytestmark = pytest.mark.anyio


async def test_public_files_router_serves_file(tmp_path: Path) -> None:
    """Verify files in the public directory are served verbatim under /static."""
    # Given a file in a public directory served by the router
    (tmp_path / "asset.txt").write_text("static asset body", encoding="utf-8")
    app = Litestar(route_handlers=[create_public_files_router(tmp_path)])

    # When it is requested under /static
    async with AsyncTestClient(app=app) as client:
        response = await client.get("/static/asset.txt")

    # Then it is served verbatim
    assert response.status_code == 200
    assert response.text == "static asset body"
