"""Response-cache generation guard middleware.

A cached GET can read the database before a concurrent write commits, then cache its
response after that write flushed the cache. The stale response would then be served
until it expires. This middleware reads the flush generations of the response's cache
indexes before the handler runs and again after the response is cached, and deletes
the entry when a flush ran in between.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar import Request
from litestar.enums import ScopeType
from litestar.handlers import HTTPRouteHandler
from litestar.middleware import ASGIMiddleware
from litestar.utils.scope.state import ScopeState

if TYPE_CHECKING:
    from litestar.types import ASGIApp, Receive, Scope, Send

__all__ = ("ResponseCacheGenerationMiddleware", "response_cache_generation_middleware")


class ResponseCacheGenerationMiddleware(ASGIMiddleware):
    """Drop a cached response when its cache was flushed while the request ran."""

    scopes = (ScopeType.HTTP,)

    async def handle(self, scope: Scope, receive: Receive, send: Send, next_app: ASGIApp) -> None:
        """Compare cache generations around a cached GET and drop a response a flush outdated.

        Args:
            scope (Scope): The ASGI connection scope.
            receive (Receive): The ASGI receive function.
            send (Send): The ASGI send function.
            next_app (ASGIApp): The next ASGI application in the middleware stack to call.
        """
        route_handler = scope.get("route_handler")
        if (
            scope.get("method") != "GET"
            or not isinstance(route_handler, HTTPRouteHandler)
            or not route_handler.cache
        ):
            await next_app(scope, receive, send)
            return

        cache_config = scope["litestar_app"].response_cache_config
        store = cache_config.get_store_from_app(scope["litestar_app"])
        generations = getattr(store, "generations", None)
        if generations is None:
            await next_app(scope, receive, send)
            return

        request: Request[Any, Any, Any] = Request(scope)
        key = (route_handler.cache_key_builder or cache_config.key_builder)(request)
        before = await generations(key)

        await next_app(scope, receive, send)

        # Litestar sets do_cache only for a response it stored, never for a cache hit.
        # The check runs after the write: a flush bumps the generation before it deletes,
        # so either its delete removed this entry or this read sees the new generation.
        stored = ScopeState.from_scope(scope).do_cache is True
        if stored and await generations(key) != before:
            await store.delete(key)


response_cache_generation_middleware = ResponseCacheGenerationMiddleware()
