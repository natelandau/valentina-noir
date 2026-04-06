"""Proxy headers middleware.

Rewrite the ASGI scope ``client`` tuple so that downstream middleware (logging,
rate limiting) sees the real client IP instead of the reverse-proxy's internal
address.

Checks headers in priority order:
  1. CF-Connecting-IP  (Cloudflare)
  2. X-Real-IP         (Railway, nginx)
  3. X-Forwarded-For   (standard; first address is the original client)
  4. Falls back to the existing scope["client"]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from litestar.enums import ScopeType
from litestar.middleware import ASGIMiddleware

if TYPE_CHECKING:
    from litestar.types import ASGIApp, Receive, Scope, Send

__all__ = ("ProxyHeadersMiddleware", "proxy_headers_middleware")

# Checked in order — first match wins
_REAL_IP_HEADERS: tuple[bytes, ...] = (
    b"cf-connecting-ip",
    b"x-real-ip",
    b"x-forwarded-for",
)
_REAL_IP_HEADER_SET: frozenset[bytes] = frozenset(_REAL_IP_HEADERS)


class ProxyHeadersMiddleware(ASGIMiddleware):
    """Replace ``scope["client"]`` with the real client IP from proxy headers.

    Must be placed **before** any middleware that reads the client address
    (logging, rate limiting, etc.).
    """

    scopes = (ScopeType.HTTP,)

    async def handle(self, scope: Scope, receive: Receive, send: Send, next_app: ASGIApp) -> None:
        """Overwrite the client address from trusted proxy headers.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive function.
            send: The ASGI send function.
            next_app: The next ASGI application in the middleware stack to call.
        """
        # Collect matching headers in a single pass, then pick by priority
        found: dict[bytes, bytes] = {}
        for header_name, header_value in scope.get("headers", []):
            if header_name in _REAL_IP_HEADER_SET and header_name not in found:
                found[header_name] = header_value

        real_ip: str | None = None
        for header_name in _REAL_IP_HEADERS:
            if header_name in found:
                decoded = found[header_name].decode("latin-1").strip()
                # X-Forwarded-For can be a comma-separated list; take the first (leftmost) IP
                real_ip = decoded.split(",")[0].strip()
                break

        if real_ip:
            client = scope.get("client")
            scope["client"] = (real_ip, client[1] if client else 0)

        await next_app(scope, receive, send)


proxy_headers_middleware = ProxyHeadersMiddleware()
