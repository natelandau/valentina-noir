"""Proxy headers middleware.

Rewrite the ASGI scope ``client`` tuple so that downstream middleware (logging,
rate limiting) sees the real client IP instead of the reverse-proxy's internal
address.

Only the header named by ``settings.server.client_ip_header`` is read, and only when the
connecting peer is in ``settings.server.trusted_proxies``. Callers can send any header, so
trusting it from any peer, or trusting one the edge proxy does not overwrite, would let
them pick their own address. When the peer is untrusted or the header is absent or
invalid, the existing ``scope["client"]`` is kept.
"""

from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING

from litestar.enums import ScopeType
from litestar.middleware import ASGIMiddleware

from vapi.config import settings

if TYPE_CHECKING:
    from collections.abc import Iterable

    from litestar.types import ASGIApp, Receive, Scope, Send

__all__ = ("ProxyHeadersMiddleware", "proxy_headers_middleware")


class ProxyHeadersMiddleware(ASGIMiddleware):
    """Replace ``scope["client"]`` with the real client IP from the trusted proxy header.

    Must be placed **before** any middleware that reads the client address
    (logging, rate limiting, etc.).
    """

    scopes = (ScopeType.HTTP,)

    async def handle(self, scope: Scope, receive: Receive, send: Send, next_app: ASGIApp) -> None:
        """Overwrite the client address from the trusted proxy header.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive function.
            send: The ASGI send function.
            next_app: The next ASGI application in the middleware stack to call.
        """
        client = scope.get("client")
        trusted_header = settings.server.client_ip_header.strip().lower().encode("latin-1")
        if client and trusted_header and _is_trusted_peer(client[0]):
            real_ip = _client_ip_from_headers(scope.get("headers", []), trusted_header)
            if real_ip:
                scope["client"] = (real_ip, client[1])

        await next_app(scope, receive, send)


def _is_trusted_peer(host: str) -> bool:
    """Return whether the connecting peer is a proxy allowed to set the client IP header."""
    address = _parse_ip(host)
    if address is None:
        return False
    return any(address in network for network in settings.server.trusted_proxies)


def _client_ip_from_headers(
    headers: Iterable[tuple[bytes, bytes]], trusted_header: bytes
) -> str | None:
    """Return the valid IP address the nearest proxy added to the trusted header, or None."""
    # A proxy that appends adds its line, or its comma entry, after the caller's, so the
    # rightmost entry of the last line is the only one a caller cannot forge.
    last_value: bytes | None = None
    for name, value in headers:
        if name == trusted_header:
            last_value = value
    if last_value is None:
        return None
    address = _parse_ip(last_value.decode("latin-1").split(",")[-1].strip())
    return str(address) if address is not None else None


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Return the address in value, unwrapping IPv4-mapped IPv6, or None when invalid."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


proxy_headers_middleware = ProxyHeadersMiddleware()
