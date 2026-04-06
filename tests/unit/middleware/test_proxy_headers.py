"""Unit tests for ProxyHeadersMiddleware."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from vapi.middleware.proxy_headers import ProxyHeadersMiddleware

pytestmark = pytest.mark.anyio


def _make_scope(
    headers: list[tuple[bytes, bytes]] | None = None,
    client: tuple[str, int] | None = ("100.64.0.17", 44358),
) -> dict[str, Any]:
    """Create a minimal ASGI HTTP scope for testing."""
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/test",
        "headers": headers or [],
        "state": {},
    }
    if client is not None:
        scope["client"] = client
    return scope


async def _run_middleware(scope: dict[str, Any]) -> dict[str, Any]:
    """Run the middleware and return the scope as seen by the next app."""
    middleware = ProxyHeadersMiddleware()
    captured_scope: dict[str, Any] = {}

    async def mock_next_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        captured_scope.update(scope)

    await middleware.handle(scope, AsyncMock(), AsyncMock(), mock_next_app)
    return captured_scope


class TestCFConnectingIP:
    """Test CF-Connecting-IP header handling."""

    async def test_cf_connecting_ip_rewrites_client(self) -> None:
        """Verify CF-Connecting-IP overwrites scope client address."""
        # Given a request with CF-Connecting-IP header
        scope = _make_scope(headers=[(b"cf-connecting-ip", b"203.0.113.42")])

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the client IP is rewritten
        assert result["client"] == ("203.0.113.42", 44358)

    async def test_cf_connecting_ip_takes_priority_over_others(self) -> None:
        """Verify CF-Connecting-IP wins when all proxy headers are present."""
        # Given a request with all three proxy headers
        scope = _make_scope(
            headers=[
                (b"x-forwarded-for", b"10.0.0.1, 10.0.0.2"),
                (b"x-real-ip", b"172.16.0.1"),
                (b"cf-connecting-ip", b"203.0.113.42"),
            ]
        )

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then CF-Connecting-IP takes priority
        assert result["client"][0] == "203.0.113.42"


class TestXRealIP:
    """Test X-Real-IP header handling."""

    async def test_x_real_ip_rewrites_client(self) -> None:
        """Verify X-Real-IP overwrites scope client address."""
        # Given a request with X-Real-IP header
        scope = _make_scope(headers=[(b"x-real-ip", b"198.51.100.7")])

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the client IP is rewritten
        assert result["client"] == ("198.51.100.7", 44358)

    async def test_x_real_ip_takes_priority_over_forwarded_for(self) -> None:
        """Verify X-Real-IP wins over X-Forwarded-For."""
        # Given a request with both X-Real-IP and X-Forwarded-For
        scope = _make_scope(
            headers=[
                (b"x-forwarded-for", b"10.0.0.1"),
                (b"x-real-ip", b"198.51.100.7"),
            ]
        )

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then X-Real-IP takes priority
        assert result["client"][0] == "198.51.100.7"


class TestXForwardedFor:
    """Test X-Forwarded-For header handling."""

    async def test_x_forwarded_for_rewrites_client(self) -> None:
        """Verify X-Forwarded-For overwrites scope client address."""
        # Given a request with X-Forwarded-For header
        scope = _make_scope(headers=[(b"x-forwarded-for", b"203.0.113.50")])

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the client IP is rewritten
        assert result["client"] == ("203.0.113.50", 44358)

    async def test_x_forwarded_for_uses_first_ip(self) -> None:
        """Verify only the first (leftmost) IP from X-Forwarded-For is used."""
        # Given a request with a multi-hop X-Forwarded-For chain
        scope = _make_scope(
            headers=[(b"x-forwarded-for", b"203.0.113.50, 70.41.3.18, 150.172.238.178")]
        )

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the first IP is used
        assert result["client"][0] == "203.0.113.50"

    async def test_x_forwarded_for_strips_whitespace(self) -> None:
        """Verify whitespace around IPs in X-Forwarded-For is stripped."""
        # Given a request with whitespace-padded X-Forwarded-For
        scope = _make_scope(headers=[(b"x-forwarded-for", b"  203.0.113.50 , 10.0.0.1 ")])

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then whitespace is stripped
        assert result["client"][0] == "203.0.113.50"


class TestFallbackBehavior:
    """Test behavior when no proxy headers are present."""

    async def test_no_proxy_headers_preserves_original_client(self) -> None:
        """Verify original client is preserved when no proxy headers exist."""
        # Given a request with no proxy headers
        scope = _make_scope(headers=[(b"content-type", b"application/json")])

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the original client is unchanged
        assert result["client"] == ("100.64.0.17", 44358)

    async def test_empty_headers_preserves_original_client(self) -> None:
        """Verify original client is preserved with empty headers."""
        # Given a request with no headers at all
        scope = _make_scope()

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the original client is unchanged
        assert result["client"] == ("100.64.0.17", 44358)

    async def test_no_client_in_scope_uses_port_zero(self) -> None:
        """Verify port defaults to 0 when scope has no client."""
        # Given a request with a proxy header but no existing client
        scope = _make_scope(
            headers=[(b"x-real-ip", b"198.51.100.7")],
            client=None,
        )

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the client is set with port 0
        assert result["client"] == ("198.51.100.7", 0)

    async def test_port_preserved_from_original_client(self) -> None:
        """Verify the original port is preserved when rewriting the IP."""
        # Given a request with a specific port
        scope = _make_scope(
            headers=[(b"cf-connecting-ip", b"203.0.113.42")],
            client=("100.64.0.17", 9999),
        )

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the port is preserved from the original client
        assert result["client"] == ("203.0.113.42", 9999)


class TestNextAppCalled:
    """Test that the next ASGI app is always invoked."""

    async def test_next_app_called_with_proxy_header(self) -> None:
        """Verify next_app is called when a proxy header is present."""
        # Given a request with a proxy header
        scope = _make_scope(headers=[(b"x-real-ip", b"198.51.100.7")])
        middleware = ProxyHeadersMiddleware()
        next_app = AsyncMock()

        # When the middleware handles the request
        await middleware.handle(scope, AsyncMock(), AsyncMock(), next_app)

        # Then next_app is called exactly once
        next_app.assert_awaited_once()

    async def test_next_app_called_without_proxy_header(self) -> None:
        """Verify next_app is called when no proxy header is present."""
        # Given a request without proxy headers
        scope = _make_scope()
        middleware = ProxyHeadersMiddleware()
        next_app = AsyncMock()

        # When the middleware handles the request
        await middleware.handle(scope, AsyncMock(), AsyncMock(), next_app)

        # Then next_app is called exactly once
        next_app.assert_awaited_once()
