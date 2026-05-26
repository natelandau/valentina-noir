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

    @pytest.mark.parametrize(
        ("status_code", "body_parts"),
        [
            (400, [b"bad request"]),
            (200, [b"x" * (IDEMPOTENCY_MAX_CACHED_BODY_BYTES + 1)]),
        ],
        ids=["non_2xx", "oversized"],
    )
    async def test_skips_caching(
        self, status_code: int, body_parts: list[bytes], mocker: MockerFixture
    ) -> None:
        """Verify non-2xx and oversized responses are not written to the cache."""
        # Given a captured response that must not be cached (bad status or too large)
        capture, store = self._build_capture(mocker, status_code=status_code, body_parts=body_parts)

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
