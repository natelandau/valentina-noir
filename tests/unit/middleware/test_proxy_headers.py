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

    async def test_ipv4_mapped_address_is_unwrapped(self) -> None:
        """Verify an IPv4-mapped header value resolves to the same address as plain IPv4."""
        # Given a request whose trusted header holds an IPv4-mapped IPv6 address
        scope = _make_scope(headers=[(b"x-real-ip", b"::ffff:198.51.100.7")])

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the plain IPv4 address is used
        assert result["client"] == ("198.51.100.7", 44358)

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


class TestTrustedPeer:
    """Test that the header is used only when the connecting peer is a trusted proxy."""

    @pytest.mark.parametrize(
        "peer",
        ["203.0.113.5", "2001:db8::5", "testclient"],
        ids=["public-ipv4", "public-ipv6", "not-an-ip"],
    )
    async def test_untrusted_peer_keeps_socket_address(self, peer: str) -> None:
        """Verify a peer outside the trusted networks cannot choose its address."""
        # Given a request from an untrusted peer that sends X-Real-IP
        scope = _make_scope(headers=[(b"x-real-ip", b"198.51.100.7")], client=(peer, 5000))

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the socket address is kept
        assert result["client"] == (peer, 5000)

    @pytest.mark.parametrize(
        "peer",
        [
            "10.251.215.226",
            "fd12:632a:abc8:1:3000:13b:ca28:50de",
            "::ffff:100.64.0.17",
            "127.0.0.1",
        ],
        ids=["private-ipv4", "railway-private-ipv6", "ipv4-mapped-cgnat", "loopback"],
    )
    async def test_trusted_peer_header_is_used(self, peer: str) -> None:
        """Verify the default trusted networks cover private, CGNAT, and loopback peers."""
        # Given a request from a peer on a default trusted network
        scope = _make_scope(headers=[(b"x-real-ip", b"198.51.100.7")], client=(peer, 5000))

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the header's address is used
        assert result["client"] == ("198.51.100.7", 5000)

    async def test_no_client_in_scope_keeps_scope(self) -> None:
        """Verify a scope without a peer address never trusts the header."""
        # Given a request with the trusted header but no connecting peer
        scope = _make_scope(headers=[(b"x-real-ip", b"198.51.100.7")], client=None)

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then no client address is invented
        assert "client" not in result

    async def test_empty_trusted_networks_trust_no_peer(self, mocker: MockerFixture) -> None:
        """Verify an empty trusted network list keeps every socket address."""
        # Given no trusted proxy networks
        mocker.patch.object(settings.server, "trusted_proxies", new=[])
        scope = _make_scope(headers=[(b"x-real-ip", b"198.51.100.7")])

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the connecting peer's address is kept
        assert result["client"] == _PEER


class TestDuplicateHeaderLines:
    """Test that repeated header lines resolve to the value the nearest proxy added."""

    async def test_last_line_wins(self) -> None:
        """Verify a caller's line before the edge's line cannot set the address."""
        # Given a caller line followed by the edge's appended line
        scope = _make_scope(headers=[(b"x-real-ip", b"192.0.2.10"), (b"x-real-ip", b"192.0.2.20")])

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the last line's address is used
        assert result["client"] == ("192.0.2.20", 44358)

    async def test_invalid_last_line_keeps_socket_address(self) -> None:
        """Verify an invalid last line does not fall back to an earlier caller line."""
        # Given a valid first line and an invalid last line
        scope = _make_scope(headers=[(b"x-real-ip", b"192.0.2.10"), (b"x-real-ip", b"garbage")])

        # When the middleware handles the request
        result = await _run_middleware(scope)

        # Then the connecting peer's address is kept
        assert result["client"] == _PEER


async def test_next_app_always_called() -> None:
    """Verify next_app is called whether or not a proxy header is present."""
    # Given a request without proxy headers
    middleware = ProxyHeadersMiddleware()
    next_app = AsyncMock()

    # When the middleware handles the request
    await middleware.handle(_make_scope(), AsyncMock(), AsyncMock(), next_app)

    # Then next_app is called exactly once
    next_app.assert_awaited_once()
