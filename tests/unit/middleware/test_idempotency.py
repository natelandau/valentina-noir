"""Unit tests for idempotency middleware scope-state and response-caching behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from litestar import Litestar, Request, post
from litestar.testing import TestClient

from vapi.constants import (
    IDEMPOTENCY_KEY_HEADER,
    IDEMPOTENCY_KEY_STATE_KEY,
    IDEMPOTENCY_MAX_CACHED_BODY_BYTES,
)
from vapi.middleware.idempotency import ResponseCapture, idempotency_middleware

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture


@post("/thing")
async def _create(data: dict, request: Request) -> dict:
    """Echo back whatever idempotency key the middleware stashed on scope state."""
    return {"stashed": request.scope["state"].get(IDEMPOTENCY_KEY_STATE_KEY)}


def _build_app() -> Litestar:
    return Litestar(route_handlers=[_create], middleware=[idempotency_middleware])


def test_idempotency_key_stashed_on_scope_state() -> None:
    """Verify the idempotency key is written to scope state for downstream logging."""
    # Given an app with the idempotency middleware and a route that reads scope state
    app = _build_app()

    # When a POST carries an Idempotency-Key header
    with TestClient(app=app) as client:
        response = client.post("/thing", json={"x": 1}, headers={IDEMPOTENCY_KEY_HEADER: "idem-1"})

    # Then the key is present on scope state during handler execution
    assert response.json()["stashed"] == "idem-1"


def test_idempotency_key_absent_when_header_missing() -> None:
    """Verify scope state has no idempotency key when the header is absent."""
    # Given an app with the idempotency middleware
    app = _build_app()

    # When a POST carries no Idempotency-Key header
    with TestClient(app=app) as client:
        response = client.post("/thing", json={"x": 1})

    # Then no idempotency key is stashed
    assert response.json()["stashed"] is None


@pytest.mark.anyio
class TestResponseCaptureCaching:
    """Tests for ResponseCapture._cache_response write/skip decisions."""

    @staticmethod
    def _build_capture(
        mocker: MockerFixture, *, status_code: int, body_parts: list[bytes]
    ) -> tuple[ResponseCapture, MagicMock]:
        """Build a ResponseCapture with a mocked store and the given captured state."""
        store = mocker.MagicMock()
        store.set = mocker.AsyncMock()
        capture = ResponseCapture(
            send=mocker.AsyncMock(),
            store=store,
            cache_key="idem-key",
            request_body_hash="body-hash",
        )
        capture._status_code = status_code
        capture._raw_headers = [(b"content-type", b"application/json")]
        capture._body_parts = body_parts
        return capture, store

    async def test_skips_caching_non_2xx_response(self, mocker: MockerFixture) -> None:
        """Verify non-2xx responses are not cached so a transient failure cannot persist."""
        # Given a captured 400 response
        capture, store = self._build_capture(mocker, status_code=400, body_parts=[b"bad request"])

        # When the response is finalized
        await capture._cache_response()

        # Then nothing is written to the store
        store.set.assert_not_called()

    async def test_skips_caching_oversized_response(self, mocker: MockerFixture) -> None:
        """Verify responses larger than the size limit are not cached."""
        # Given a 2xx response one byte over the cache size limit
        oversized = [b"x" * (IDEMPOTENCY_MAX_CACHED_BODY_BYTES + 1)]
        capture, store = self._build_capture(mocker, status_code=200, body_parts=oversized)

        # When the response is finalized
        await capture._cache_response()

        # Then nothing is written to the store
        store.set.assert_not_called()

    async def test_caches_small_2xx_response(self, mocker: MockerFixture) -> None:
        """Verify a small 2xx response is written to the store."""
        # Given a small 2xx JSON response
        capture, store = self._build_capture(mocker, status_code=200, body_parts=[b'{"ok": true}'])

        # When the response is finalized
        await capture._cache_response()

        # Then it is written to the store exactly once
        store.set.assert_awaited_once()
