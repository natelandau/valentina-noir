"""Proxy headers middleware.

Rewrite the ASGI scope ``client`` tuple so that downstream middleware (logging,
rate limiting) sees the real client IP instead of the reverse-proxy's internal
address.

Only the header named by ``settings.server.client_ip_header`` is trusted. Callers can
send any header, so trusting one the edge proxy does not overwrite would let them pick
their own address. When the header is absent or invalid, the existing
``scope["client"]`` is kept.
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
        trusted_header = settings.server.client_ip_header.strip().lower().encode("latin-1")
        if trusted_header:
            real_ip = _client_ip_from_headers(scope.get("headers", []), trusted_header)
            if real_ip:
                client = scope.get("client")
                scope["client"] = (real_ip, client[1] if client else 0)

        await next_app(scope, receive, send)


def _client_ip_from_headers(
    headers: Iterable[tuple[bytes, bytes]], trusted_header: bytes
) -> str | None:
    """Return the valid IP address in the trusted header, or None."""
    for header_name, header_value in headers:
        if header_name != trusted_header:
            continue
        # A list-valued header (X-Forwarded-For) gains its rightmost entry from the
        # nearest proxy; earlier entries come from the caller.
        candidate = header_value.decode("latin-1").split(",")[-1].strip()
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            return None
    return None


proxy_headers_middleware = ProxyHeadersMiddleware()
