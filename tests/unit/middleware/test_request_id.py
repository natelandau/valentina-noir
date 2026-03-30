"""Unit tests for RequestIdMiddleware."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from vapi.constants import REQUEST_ID_HEADER, REQUEST_ID_STATE_KEY

pytestmark = pytest.mark.anyio


def _make_scope() -> dict[str, Any]:
    """Create a minimal ASGI HTTP scope for testing."""
    return {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/test",
        "headers": [],
        "state": {},
    }


async def _collect_response_headers(
    middleware_handle: Any, scope: dict[str, Any]
) -> dict[str, str]:
    """Run middleware and collect response headers from the send wrapper."""
    captured_headers: dict[str, str] = {}

    async def mock_next_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})

    receive = AsyncMock()

    sent_messages: list[dict[str, Any]] = []

    async def capturing_send(message: dict[str, Any]) -> None:
        sent_messages.append(message)

    await middleware_handle(scope, receive, capturing_send, mock_next_app)

    for msg in sent_messages:
        if msg["type"] == "http.response.start":
            for raw_key, raw_value in msg.get("headers", []):
                header_name = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
                header_value = raw_value.decode() if isinstance(raw_value, bytes) else raw_value
                captured_headers[header_name] = header_value

    return captured_headers


class TestRequestIdMiddlewareGeneration:
    """Test request ID generation and scope storage."""

    async def test_generates_request_id_on_scope(self) -> None:
        """Verify middleware stores a request ID in scope state."""
        from vapi.middleware.request_id import RequestIdMiddleware

        # Given a fresh HTTP scope
        scope = _make_scope()
        middleware = RequestIdMiddleware()

        # When the middleware handles the request
        async def mock_next_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        await middleware.handle(scope, AsyncMock(), AsyncMock(), mock_next_app)

        # Then a request ID is stored in scope state
        assert REQUEST_ID_STATE_KEY in scope["state"]
        assert scope["state"][REQUEST_ID_STATE_KEY].startswith("req_")

    async def test_request_id_format(self) -> None:
        """Verify request ID has correct prefix and reasonable length."""
        from vapi.middleware.request_id import RequestIdMiddleware

        # Given a fresh HTTP scope
        scope = _make_scope()
        middleware = RequestIdMiddleware()

        # When the middleware handles the request
        async def mock_next_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        await middleware.handle(scope, AsyncMock(), AsyncMock(), mock_next_app)

        # Then the ID has the correct format
        request_id = scope["state"][REQUEST_ID_STATE_KEY]
        assert request_id.startswith("req_")
        assert 20 <= len(request_id) <= 30

    async def test_unique_ids_per_request(self) -> None:
        """Verify two requests produce different IDs."""
        from vapi.middleware.request_id import RequestIdMiddleware

        middleware = RequestIdMiddleware()

        async def mock_next_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        # Given two separate requests
        scope1 = _make_scope()
        scope2 = _make_scope()

        # When both are handled
        await middleware.handle(scope1, AsyncMock(), AsyncMock(), mock_next_app)
        await middleware.handle(scope2, AsyncMock(), AsyncMock(), mock_next_app)

        # Then the IDs are different
        assert scope1["state"][REQUEST_ID_STATE_KEY] != scope2["state"][REQUEST_ID_STATE_KEY]


class TestRequestIdMiddlewareResponseHeader:
    """Test X-Request-Id response header injection."""

    async def test_header_set_on_response(self) -> None:
        """Verify X-Request-Id header is present in the response."""
        from vapi.middleware.request_id import RequestIdMiddleware

        # Given a fresh HTTP scope
        scope = _make_scope()
        middleware = RequestIdMiddleware()

        # When the middleware handles the request
        headers = await _collect_response_headers(middleware.handle, scope)

        # Then X-Request-Id header is present and matches scope state
        # MutableScopeHeaders lowercases header names per HTTP spec
        header_key = REQUEST_ID_HEADER.lower()
        assert header_key in headers
        assert headers[header_key] == scope["state"][REQUEST_ID_STATE_KEY]

    async def test_header_value_matches_scope_state(self) -> None:
        """Verify the response header value matches the scope-stored ID."""
        from vapi.middleware.request_id import RequestIdMiddleware

        # Given a fresh HTTP scope
        scope = _make_scope()
        middleware = RequestIdMiddleware()

        # When the middleware handles the request
        headers = await _collect_response_headers(middleware.handle, scope)

        # Then the header and scope values are identical
        header_key = REQUEST_ID_HEADER.lower()
        assert headers[header_key] == scope["state"][REQUEST_ID_STATE_KEY]

    async def test_non_response_messages_passed_through(self) -> None:
        """Verify non-response-start messages are not modified."""
        from vapi.middleware.request_id import RequestIdMiddleware

        # Given a fresh HTTP scope
        scope = _make_scope()
        middleware = RequestIdMiddleware()
        sent_messages: list[dict[str, Any]] = []

        async def mock_next_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"hello"})

        async def capturing_send(message: dict[str, Any]) -> None:
            sent_messages.append(message)

        # When the middleware handles the request
        await middleware.handle(scope, AsyncMock(), capturing_send, mock_next_app)

        # Then body messages are passed through unchanged
        body_msg = [m for m in sent_messages if m["type"] == "http.response.body"]
        assert len(body_msg) == 1
        assert body_msg[0]["body"] == b"hello"
