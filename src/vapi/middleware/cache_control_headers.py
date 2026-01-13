"""Cache control header middleware."""

from __future__ import annotations

from typing import TYPE_CHECKING

from litestar.datastructures import MutableScopeHeaders
from litestar.enums import ScopeType
from litestar.middleware import ASGIMiddleware

from vapi.config import settings

if TYPE_CHECKING:
    from litestar.types import ASGIApp, Message, Receive, Scope, Send

__all__ = ("CacheControlMiddleware",)


class CacheControlMiddleware(ASGIMiddleware):
    """Add Cache-Control headers to responses for cached routes."""

    scopes = (ScopeType.HTTP,)

    def __init__(self, *, max_age: int = settings.stores.ttl, private: bool = True) -> None:
        self.max_age = max_age
        self.private = private

    async def handle(self, scope: Scope, receive: Receive, send: Send, next_app: ASGIApp) -> None:
        """Add Cache-Control header if route has caching enabled."""
        route_handler = scope.get("route_handler")
        cache_value = route_handler.opt.get("http_cache", None)

        # Fall back to cache attribute if http_cache not set
        if cache_value is None:
            cache_value = getattr(route_handler, "cache", None)

        # Only add headers if caching is explicitly enabled (True or int)
        if cache_value is None or cache_value is False:
            cache_header_value = "no-cache"
        else:
            max_age = self.max_age if isinstance(cache_value, bool) else cache_value

            visibility = "private" if self.private else "public"
            cache_header_value = f"{visibility}, max-age={max_age}"

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                headers = MutableScopeHeaders(message)
                headers["Cache-Control"] = cache_header_value

            await send(message)

        await next_app(scope, receive, send_wrapper)


cache_control_middleware = CacheControlMiddleware(max_age=settings.stores.ttl, private=True)
