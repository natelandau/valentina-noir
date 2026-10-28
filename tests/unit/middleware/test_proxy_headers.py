"""Unit tests for ProxyHeadersMiddleware."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

from vapi.config import settings
from vapi.middleware.proxy_headers import ProxyHeadersMiddleware

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio

_PEER = ("100.64.0.17", 44358)


def _make_scope(
    headers: list[tuple[bytes, bytes]] | None = None,
    client: tuple[str, int] | None = _PEER,
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


class TestTrustedHeader:
    """Test that only the configured header sets the client address."""

    async def test_trusted_header_rewrites_client(self) -> None:
        """Verify the default trusted header, X-Real-IP, overwrites the client address."""
        # Given a request with X-Real-IP
        scope = _make_scope(headers=[(b"x-real-ip", b"198.51.100.7")])

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the client IP is rewritten and the port kept
        assert result["client"] == ("198.51.100.7", 44358)

    @pytest.mark.parametrize(
        "header",
        [(b"cf-connecting-ip", b"203.0.113.42"), (b"x-forwarded-for", b"203.0.113.42")],
        ids=["cf-connecting-ip", "x-forwarded-for"],
    )
    async def test_untrusted_headers_are_ignored(self, header: tuple[bytes, bytes]) -> None:
        """Verify a caller cannot choose its address with a header the edge does not set."""
        # Given a request carrying only an untrusted client-IP header
        scope = _make_scope(headers=[header])

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the connecting peer's address is kept
        assert result["client"] == _PEER

    async def test_invalid_address_is_ignored(self) -> None:
        """Verify a trusted header that is not an IP address leaves the client unchanged."""
        # Given a request whose trusted header is not an IP
        scope = _make_scope(headers=[(b"x-real-ip", b"not-an-ip")])

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the connecting peer's address is kept
        assert result["client"] == _PEER

    async def test_configured_list_header_uses_rightmost_entry(self, mocker: MockerFixture) -> None:
        """Verify a list-valued trusted header uses the entry added by the nearest proxy."""
        # Given X-Forwarded-For is the trusted header and the caller prepended a fake entry
        mocker.patch.object(settings.server, "client_ip_header", new="X-Forwarded-For")
        scope = _make_scope(headers=[(b"x-forwarded-for", b"6.6.6.6, 198.51.100.7")])

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the rightmost address is used
        assert result["client"] == ("198.51.100.7", 44358)

    async def test_empty_setting_trusts_no_header(self, mocker: MockerFixture) -> None:
        """Verify an empty setting keeps the connecting peer's address."""
        # Given no trusted header is configured
        mocker.patch.object(settings.server, "client_ip_header", new="")
        scope = _make_scope(headers=[(b"x-real-ip", b"198.51.100.7")])

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the connecting peer's address is kept
        assert result["client"] == _PEER

    async def test_no_client_in_scope_uses_port_zero(self) -> None:
        """Verify port defaults to 0 when scope has no client."""
        # Given a request with the trusted header but no existing client
        scope = _make_scope(headers=[(b"x-real-ip", b"198.51.100.7")], client=None)

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the client is set with port 0
        assert result["client"] == ("198.51.100.7", 0)


async def test_next_app_always_called() -> None:
    """Verify next_app is called whether or not a proxy header is present."""
    # Given a request without proxy headers
    middleware = ProxyHeadersMiddleware()
    next_app = AsyncMock()

    # When the middleware handles the request
    await middleware.handle(_make_scope(), AsyncMock(), AsyncMock(), next_app)

    # Then next_app is called exactly once
    next_app.assert_awaited_once()
