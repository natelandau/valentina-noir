"""Idempotency key middleware.

Provide idempotency support for POST/PUT/PATCH requests by caching responses keyed by a
user-provided Idempotency-Key header. When a duplicate request is received with the same
idempotency key, the cached response is returned instead of processing the request again.

If a request is received with the same idempotency key but a different request body,
a ConflictError is raised to prevent unintended behavior from reusing idempotency keys.
A request that arrives while another with the same key is still running also gets a
ConflictError, so concurrent duplicates never both execute.

This middleware automatically applies to all POST/PUT/PATCH requests that include an
Idempotency-Key header. Routes flagged with the ``SENSITIVE_RESPONSE_OPT_KEY`` opt are
skipped, so a secret in their response is never written to the cache.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from litestar.enums import ScopeType
from litestar.middleware import ASGIMiddleware
from litestar.serialization import decode_json, encode_json
from msgspec import Struct

from vapi.config import settings
from vapi.constants import (
    AUTH_HEADER_KEY,
    IDEMPOTENCY_IN_FLIGHT_TTL_SECONDS,
    IDEMPOTENCY_KEY_HEADER,
    IDEMPOTENCY_KEY_MAX_LENGTH,
    IDEMPOTENCY_KEY_STATE_KEY,
    IDEMPOTENCY_MAX_CACHED_BODY_BYTES,
    IDEMPOTENCY_TTL_SECONDS,
    ON_BEHALF_OF_HEADER_KEY,
    SENSITIVE_RESPONSE_OPT_KEY,
)
from vapi.lib.crypt import hmac_sha256_hex
from vapi.lib.exceptions import ConflictError, ValidationError
from vapi.lib.stores import claim_store_key

if TYPE_CHECKING:
    from collections.abc import Iterable

    from litestar import Request
    from litestar.stores.base import Store
    from litestar.types import ASGIApp, Message, Receive, Scope, Send
    from litestar.types.asgi_types import (
        HTTPRequestEvent,
        HTTPResponseBodyEvent,
    )

logger = logging.getLogger("vapi")

__all__ = ("IdempotencyMiddleware", "idempotency_middleware")

IN_PROGRESS_DETAIL = "A request with this idempotency key is still in progress."


def _validate_idempotency_key(idempotency_key: str) -> None:
    """Refuse an idempotency key that is too long or has non-visible characters.

    The key becomes part of the cache key and the request log, so it is bounded to
    visible ASCII (no whitespace or control characters).

    Args:
        idempotency_key (str): The Idempotency-Key header value.

    Raises:
        ValidationError: If the key is longer than the limit or has a disallowed character.
    """
    if len(idempotency_key) <= IDEMPOTENCY_KEY_MAX_LENGTH and all(
        "!" <= char <= "~" for char in idempotency_key
    ):
        return
    message = (
        f"Must be 1 to {IDEMPOTENCY_KEY_MAX_LENGTH} visible ASCII characters "
        "with no spaces or control characters."
    )
    raise ValidationError(
        detail=f"Invalid {IDEMPOTENCY_KEY_HEADER} header",
        invalid_parameters=[{"field": IDEMPOTENCY_KEY_HEADER, "message": message}],
    )


async def _release_in_flight(*, store: Store, key: str, token: bytes) -> None:
    """Release an in-flight marker only while this request still holds it.

    A request that outlives the marker's TTL must not delete a marker a later duplicate
    has since claimed, or a third duplicate could run alongside that one.

    Args:
        store (Store): The idempotency store.
        key (str): The in-flight marker key.
        token (bytes): The value this request stored when it claimed the marker.
    """
    if await store.get(key) == token:
        await store.delete(key)


class CachedResponse(Struct, frozen=True):
    """Store cached response data for idempotency.

    Attributes:
        status_code: HTTP status code of the cached response.
        body: Base64-encoded response body.
        headers: Response headers as key-value pairs.
        request_body_hash: SHA256 hash of the original request body.
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
        method: str = scope.get("method", "")

        if method not in {"POST", "PUT", "PATCH"}:
            await next_app(scope, receive, send)
            return

        # An unmatched route (404, etc.) has no handler to dedup, so pass through
        route_handler = scope.get("route_handler")
        if route_handler is None or route_handler.opt.get(SENSITIVE_RESPONSE_OPT_KEY):
            await next_app(scope, receive, send)
            return

        app = scope["litestar_app"]
        request: Request[Any, Any, Any] = app.request_class(scope, receive)

        idempotency_key = request.headers.get(IDEMPOTENCY_KEY_HEADER)
        if not idempotency_key:
            await next_app(scope, receive, send)
            return
        _validate_idempotency_key(idempotency_key)

        # Stash on scope state so the request logger can surface it. Only the cache-miss path
        # reaches the inner logging middleware; cache hits short-circuit and aren't logged here.
        scope["state"][IDEMPOTENCY_KEY_STATE_KEY] = idempotency_key

        store = app.stores.get(settings.stores.idempotency_key)
        cache_key = self._build_cache_key(request, idempotency_key=idempotency_key, method=method)

        # Reading the ASGI stream consumes it, so buffer the body to replay to the handler;
        # the hash backs the same-key/different-body conflict check on a later duplicate.
        full_body, request_body_hash = await self._read_and_hash_body(request)
        replay_receive = self._create_body_replay(full_body)

        cached = await store.get(cache_key)
        if cached is not None:
            await self._handle_cache_hit(
                send, cached, idempotency_key, request_body_hash, cache_key, request
            )
            return

        in_flight_key = f"in_flight:{cache_key}"
        in_flight_token = uuid4().hex.encode()
        if not await claim_store_key(
            store=store,
            key=in_flight_key,
            value=in_flight_token,
            expires_in=IDEMPOTENCY_IN_FLIGHT_TTL_SECONDS,
        ):
            # The running request may have cached its response since the first lookup
            cached = await store.get(cache_key)
            if cached is not None:
                await self._handle_cache_hit(
                    send, cached, idempotency_key, request_body_hash, cache_key, request
                )
                return
            raise ConflictError(detail=IN_PROGRESS_DETAIL)

        logger.debug(
            "Idempotency cache miss",
            extra={"cache_key": cache_key, "idempotency_key": idempotency_key},
        )
        response_capture = ResponseCapture(send, store, cache_key, request_body_hash)
        try:
            await next_app(scope, replay_receive, response_capture)
        finally:
            await _release_in_flight(store=store, key=in_flight_key, token=in_flight_token)

    async def _read_and_hash_body(self, request: Request[Any, Any, Any]) -> tuple[bytes, str]:
        """Read the full request body within the route's size limit and hash it.

        Reading through ``Request.body`` applies the route's ``request_max_body_size``, so an
        oversized body is refused with 413 before it is fully buffered.

        Args:
            request (Request): The request wrapping the ASGI receive channel.

        Returns:
            tuple[bytes, str]: The full body bytes and its SHA256 hex digest.
        """
        full_body = await request.body()
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
                return {"type": "http.request", "body": full_body, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        return replay_receive

    async def _handle_cache_hit(
        self,
        send: Send,
        cached: bytes,
        idempotency_key: str,
        request_body_hash: str,
        cache_key: str,
        request: Request[Any, Any, Any],
    ) -> None:
        """Handle a cache hit by validating body hash and sending cached response.

        A replay skips the handler, so the route's guards run first: an acting user or
        developer who lost access since the original request is refused exactly as a
        live request would be.

        Args:
            send (Send): The ASGI send function.
            cached (bytes): The cached response data as JSON bytes.
            idempotency_key (str): The user-provided idempotency key.
            request_body_hash (str): SHA256 hash of the current request body.
            cache_key (str): The cache key for logging.
            request (Request): The incoming request, used to rerun the route's guards.

        Raises:
            ConflictError: If the request body hash doesn't match the cached hash.
        """
        await request.scope["route_handler"].authorize_connection(request)

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

        The cache key combines the API key fingerprint, the On-Behalf-Of user, the
        idempotency key, the method, and the path with its query string, so one acting
        user's cached response is never replayed to another.

        Args:
            request (Request): The incoming request object.
            idempotency_key (str): The user-provided idempotency key.
            method (str): The HTTP method (POST/PATCH).

        Returns:
            str: A unique cache key for this request.
        """
        api_key = request.headers.get(AUTH_HEADER_KEY, "anonymous")
        fingerprint = hmac_sha256_hex(data=api_key)[:16]
        acting_user = request.headers.get(ON_BEHALF_OF_HEADER_KEY, "")
        path = request.url.path
        query = request.url.query
        return f"{fingerprint}:{acting_user}:{idempotency_key}:{method}:{path}?{query}"

    async def _send_cached_response(self, send: Send, cached: CachedResponse) -> None:
        """Send a cached response to the client.

        Args:
            send (Send): The ASGI send function.
            cached (CachedResponse): The cached response data.
        """
        body = base64.b64decode(cached.body)
        # ASGI spec transports headers as latin-1 bytes
        headers = [(k.encode("latin-1"), v.encode("latin-1")) for k, v in cached.headers]

        await send(
            {
                "type": "http.response.start",
                "status": cached.status_code,
                "headers": headers,
            }
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
        "_raw_headers",
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
        self._raw_headers: Iterable[tuple[bytes, bytes]] = []
        self._body_parts: list[bytes] = []

    async def __call__(self, message: Message) -> None:
        """Intercept and forward ASGI messages while capturing response data.

        Args:
            message (Message): The ASGI message to process.
        """
        if message["type"] == "http.response.start":
            self._status_code = message.get("status", 200)
            self._raw_headers = message.get("headers", [])

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
        # Caching errors would let a bad request's failure persist for the TTL; clients retrying
        # after fixing a validation error would keep hitting the stale failure
        if not (200 <= self._status_code < 300):  # noqa: PLR2004
            return

        # Skip caching oversized responses to bound Redis memory and avoid buffering large
        # payloads (base64 adds ~33%) for every unique idempotency key. A retrying client
        # re-executes the handler, same as a normal cache miss
        full_body = b"".join(self._body_parts)
        if len(full_body) > IDEMPOTENCY_MAX_CACHED_BODY_BYTES:
            logger.warning(
                "Idempotency response exceeds cache size limit; skipping cache write",
                extra={
                    "cache_key": self._cache_key,
                    "body_bytes": len(full_body),
                    "limit_bytes": IDEMPOTENCY_MAX_CACHED_BODY_BYTES,
                },
            )
            return

        # ASGI spec encodes header bytes as latin-1 (RFC 7230); decode on cache-write only so
        # non-cached responses (4xx/5xx) don't pay the decode cost
        headers = [
            (
                k.decode("latin-1") if isinstance(k, bytes) else k,
                v.decode("latin-1") if isinstance(v, bytes) else v,
            )
            for k, v in self._raw_headers
        ]
        cached = CachedResponse(
            status_code=self._status_code,
            body=base64.b64encode(full_body).decode("ascii"),
            headers=headers,
            request_body_hash=self._request_body_hash,
        )
        await self._store.set(
            self._cache_key, encode_json(cached), expires_in=IDEMPOTENCY_TTL_SECONDS
        )


idempotency_middleware = IdempotencyMiddleware()
