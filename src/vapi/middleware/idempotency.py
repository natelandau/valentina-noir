"""Idempotency key middleware.

Provide idempotency support for POST/PUT/PATCH requests by caching responses keyed by a
user-provided Idempotency-Key header. When a duplicate request is received with the same
idempotency key, the cached response is returned instead of processing the request again.

If a request is received with the same idempotency key but a different request body,
a ConflictError is raised to prevent unintended behavior from reusing idempotency keys.

This middleware automatically applies to all POST/PUT/PATCH requests that include an
Idempotency-Key header. No per-route configuration is required.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import TYPE_CHECKING, Any, cast

from litestar.enums import ScopeType
from litestar.middleware import ASGIMiddleware
from litestar.serialization import decode_json, encode_json
from msgspec import Struct

from vapi.config import settings
from vapi.constants import AUTH_HEADER_KEY, IDEMPOTENCY_KEY_HEADER, IDEMPOTENCY_TTL_SECONDS
from vapi.lib.crypt import hmac_sha256_hex
from vapi.lib.exceptions import ConflictError

if TYPE_CHECKING:
    from litestar import Request
    from litestar.types import ASGIApp, Message, Receive, Scope, Send
    from litestar.types.asgi_types import (
        HTTPRequestEvent,
        HTTPResponseBodyEvent,
        HTTPResponseStartEvent,
    )

logger = logging.getLogger("vapi")

__all__ = ("IdempotencyMiddleware", "idempotency_middleware")


class CachedResponse(Struct, frozen=True):
    """Store cached response data for idempotency.

    Args:
        status_code (int): HTTP status code of the cached response.
        body (str): Base64-encoded response body.
        headers (list[tuple[str, str]]): Response headers as key-value pairs.
        request_body_hash (str): SHA256 hash of the original request body.
    """

    status_code: int
    body: str
    headers: list[tuple[str, str]]
    request_body_hash: str


class IdempotencyMiddleware(ASGIMiddleware):
    """Enforce idempotency for POST/PUT/PATCH requests using a user-provided idempotency key.

    This middleware automatically applies to all POST/PUT/PATCH requests that include an
    Idempotency-Key header. Subsequent requests with the same idempotency key return the
    cached response instead of re-processing the request.

    If the same idempotency key is reused with a different request body, a ConflictError
    is raised to prevent accidental misuse of idempotency keys.
    """

    scopes = (ScopeType.HTTP,)

    async def handle(self, scope: Scope, receive: Receive, send: Send, next_app: ASGIApp) -> None:
        """Handle ASGI call for idempotency.

        Args:
            scope (Scope): The ASGI connection scope.
            receive (Receive): The ASGI receive function.
            send (Send): The ASGI send function.
            next_app (ASGIApp): The next ASGI application in the middleware stack to call.
        """
        method: str = scope.get("method", "")  # type: ignore[assignment]

        # Only process POST/PUT/PATCH methods
        if method not in {"POST", "PUT", "PATCH"}:
            await next_app(scope, receive, send)
            return

        # Skip if no route handler (e.g., 404 requests)
        if scope.get("route_handler") is None:  # pragma: no cover
            await next_app(scope, receive, send)
            return

        app = scope["litestar_app"]
        request: Request[Any, Any, Any] = app.request_class(scope)

        idempotency_key = request.headers.get(IDEMPOTENCY_KEY_HEADER)
        if not idempotency_key:
            await next_app(scope, receive, send)
            return

        store = app.stores.get(settings.stores.idempotency_key)
        cache_key = self._build_cache_key(request, idempotency_key=idempotency_key, method=method)

        # Read request body and compute hash
        full_body, request_body_hash = await self._read_and_hash_body(receive)
        replay_receive = self._create_body_replay(full_body)

        # Check for cached response
        cached = await store.get(cache_key)
        if cached is not None:
            await self._handle_cache_hit(
                send, cached, idempotency_key, request_body_hash, cache_key
            )
            return

        # Cache miss: capture response and cache it
        logger.debug(
            "Idempotency cache miss",
            extra={"cache_key": cache_key, "idempotency_key": idempotency_key},
        )
        response_capture = ResponseCapture(send, store, cache_key, request_body_hash)
        await next_app(scope, replay_receive, response_capture)

    async def _read_and_hash_body(self, receive: Receive) -> tuple[bytes, str]:
        """Read the full request body and compute its SHA256 hash.

        Args:
            receive (Receive): The ASGI receive function.

        Returns:
            tuple[bytes, str]: The full body bytes and its SHA256 hex digest.
        """
        body_chunks: list[bytes] = []
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if body:
                    body_chunks.append(body)
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":  # pragma: no cover
                break

        full_body = b"".join(body_chunks)
        body_hash = hashlib.sha256(full_body).hexdigest()
        return full_body, body_hash

    def _create_body_replay(self, full_body: bytes) -> Receive:
        """Create a receive function that replays the buffered body.

        Args:
            full_body (bytes): The buffered request body.

        Returns:
            Receive: An ASGI receive function that returns the buffered body.
        """
        body_sent = False

        async def replay_receive() -> HTTPRequestEvent:
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return cast(
                    "HTTPRequestEvent",
                    {"type": "http.request", "body": full_body, "more_body": False},
                )
            return cast(
                "HTTPRequestEvent", {"type": "http.request", "body": b"", "more_body": False}
            )

        return replay_receive

    async def _handle_cache_hit(
        self,
        send: Send,
        cached: bytes,
        idempotency_key: str,
        request_body_hash: str,
        cache_key: str,
    ) -> None:
        """Handle a cache hit by validating body hash and sending cached response.

        Args:
            send (Send): The ASGI send function.
            cached (bytes): The cached response data as JSON bytes.
            idempotency_key (str): The user-provided idempotency key.
            request_body_hash (str): SHA256 hash of the current request body.
            cache_key (str): The cache key for logging.

        Raises:
            ConflictError: If the request body hash doesn't match the cached hash.
        """
        cached_response = decode_json(cached, target_type=CachedResponse)

        if cached_response.request_body_hash != request_body_hash:
            msg = (
                f"Idempotency key '{idempotency_key}' was previously used with a different "
                "request body. Each unique request must use a unique idempotency key."
            )
            raise ConflictError(detail=msg)

        logger.debug(
            "Idempotency cache hit",
            extra={"cache_key": cache_key, "idempotency_key": idempotency_key},
        )
        await self._send_cached_response(send, cached_response)

    def _build_cache_key(
        self,
        request: Request[Any, Any, Any],
        *,
        idempotency_key: str,
        method: str,
    ) -> str:
        """Build a unique cache key for the idempotency cache.

        The cache key combines the API key fingerprint, idempotency key, method, and path
        to ensure uniqueness per user and request.

        Args:
            request (Request): The incoming request object.
            idempotency_key (str): The user-provided idempotency key.
            method (str): The HTTP method (POST/PATCH).

        Returns:
            str: A unique cache key for this request.
        """
        api_key = request.headers.get(AUTH_HEADER_KEY, "anonymous")
        fingerprint = hmac_sha256_hex(data=api_key)[:16]
        path = request.url.path
        return f"{fingerprint}:{idempotency_key}:{method}:{path}"

    async def _send_cached_response(self, send: Send, cached: CachedResponse) -> None:
        """Send a cached response to the client.

        Args:
            send (Send): The ASGI send function.
            cached (CachedResponse): The cached response data.
        """
        body = base64.b64decode(cached.body)
        headers = [(k.encode(), v.encode()) for k, v in cached.headers]

        await send(
            cast(
                "HTTPResponseStartEvent",
                {
                    "type": "http.response.start",
                    "status": cached.status_code,
                    "headers": headers,
                },
            )
        )
        await send(cast("HTTPResponseBodyEvent", {"type": "http.response.body", "body": body}))


class ResponseCapture:
    """Capture and cache response data during the request lifecycle.

    This class wraps the ASGI send function to intercept response messages,
    capture the response data, and cache it for future idempotent requests.
    """

    __slots__ = (
        "_body_parts",
        "_cache_key",
        "_headers",
        "_request_body_hash",
        "_send",
        "_status_code",
        "_store",
    )

    def __init__(self, send: Send, store: Any, cache_key: str, request_body_hash: str) -> None:
        self._send = send
        self._store = store
        self._cache_key = cache_key
        self._request_body_hash = request_body_hash
        self._status_code: int = 200
        self._headers: list[tuple[str, str]] = []
        self._body_parts: list[bytes] = []

    async def __call__(self, message: Message) -> None:
        """Intercept and forward ASGI messages while capturing response data.

        Args:
            message (Message): The ASGI message to process.
        """
        if message["type"] == "http.response.start":
            self._status_code = message.get("status", 200)
            raw_headers = message.get("headers", [])
            self._headers = [
                (
                    k.decode() if isinstance(k, bytes) else k,
                    v.decode() if isinstance(v, bytes) else v,
                )
                for k, v in raw_headers
            ]

        elif message["type"] == "http.response.body":
            body = message.get("body", b"")
            if body:
                self._body_parts.append(body)

            # Cache on final body chunk (more_body=False or not present)
            if not message.get("more_body", False):
                await self._cache_response()

        await self._send(message)

    async def _cache_response(self) -> None:
        """Cache the captured response data."""
        # Only cache successful responses (2xx)
        if not (200 <= self._status_code < 300):  # noqa: PLR2004
            return

        full_body = b"".join(self._body_parts)
        cached = CachedResponse(
            status_code=self._status_code,
            body=base64.b64encode(full_body).decode("ascii"),
            headers=self._headers,
            request_body_hash=self._request_body_hash,
        )
        await self._store.set(
            self._cache_key, encode_json(cached), expires_in=IDEMPOTENCY_TTL_SECONDS
        )


idempotency_middleware = IdempotencyMiddleware()
