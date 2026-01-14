"""Rate limit middleware.

Implement a leaky bucket algorithm for rate limiting.

Response headers follow the IETF draft for rate limit headers specification as of Sep 2025.

https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/
"""

from __future__ import annotations

import hashlib
import hmac
import math
import time
from itertools import chain
from typing import TYPE_CHECKING, Any

from litestar.datastructures import MutableScopeHeaders
from litestar.enums import ScopeType
from litestar.middleware import ASGIMiddleware
from litestar.serialization import decode_json, encode_json
from msgspec import Struct, field

from vapi.config import settings
from vapi.constants import (
    AUTH_HEADER_KEY,
    EXCLUDE_FROM_RATE_LIMIT_KEY,
    IGNORE_RATE_LIMIT_HEADER_KEY,
)
from vapi.lib.exceptions import TooManyRequestsError
from vapi.utils.math import round_up

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import Self

    from litestar import Request
    from litestar.stores.base import Store
    from litestar.types import ASGIApp, Message, Receive, Scope, Send


class RateLimitPolicy(Struct, frozen=True):
    """Define rate limit policies for token bucket allocation and refill.

    A rate limit policy defines how tokens are allocated and refilled for a given rate limit. It can also specify header-setting behavior, and exemption rules.

    Args:
        name (str): Name of the rate limit policy.
        capacity (int): Maximum number of tokens that the bucket can hold at any time. This represents the burst capacity of the rate limit.
        refill_rate (float): Rate at which tokens are refilled, in tokens per second. For example, a value of 3 means 3 tokens are added each second until the bucket reaches its capacity.
        priority (int, optional): Priority of the rate limit when multiple policies apply. Lower values take precedence. Defaults to 0.
        set_headers (bool, optional): Whether to include the rate limit headers configured in :class:`RateLimitMiddleware` in responses. Defaults to True.
        set_429_headers (bool, optional): Whether to include the 429-related headers configured in :class:`RateLimitMiddleware` when a request is rejected due to rate limiting. Defaults to True.
        is_exempt (Callable[[Request], Awaitable[bool]], optional): Async predicate that determines if a given request is exempt from this policy. If provided and returns ``True``, the request bypasses rate limiting. Defaults to None.
    """

    name: str
    capacity: int
    refill_rate: float
    priority: int = field(default=0)
    set_headers: bool = field(default=True)
    set_429_headers: bool = field(default=True)
    is_exempt: Callable[[Request[Any, Any, Any]], Awaitable[bool]] | None = field(default=None)

    def __gt__(self, other: RateLimitPolicy) -> bool:
        """Compare two rate limit policies based on their priority."""
        return self.priority < other.priority


class BucketState(Struct, frozen=True):
    """Store the minimal state needed to persist and reconstruct a TokenBucket.

    This struct stores the minimal state needed to persist and later reconstruct a :class:`TokenBucket`.

    Args:
        tokens (float): Current number of tokens in the bucket.
        last_refill (float): Timestamp (from :func:`time.monotonic`) of the last refill operation.
    """

    tokens: float
    last_refill: float


# This can be a normal class as well, but since we already have msgspec as a dependency and
# Struct's are faster to create, and there is no need of **kwargs or something which makes
# it necessary to use a class, we are fine with a struct.
class TokenBucket(Struct):
    """Implement the token bucket algorithm for rate limiting.

    This class implements the token bucket algorithm for rate limiting, where tokens accumulate over time at a fixed rate. Each request consumes one token, and requests are allowed only if at least one token is available.

    Args:
        name (str): Name of the rate limit policy.
        store (Store): Backend store used to persist bucket state.
        storage_key (str): Unique key under which the bucket is stored.
        request_identifier (str): Unique identifier for the request.
        capacity (int): Maximum number of tokens the bucket can hold.
        refill_rate (float): Rate at which tokens are refilled (tokens per second).
        tokens (float): Current number of tokens in the bucket.
        last_refill (float): Timestamp of the last refill. Defaults to time.monotonic().
        set_headers (bool): Whether to set the rate limit headers in the response.
        set_429_headers (bool): Whether to set the 429-related headers in the response.
    """

    # storage related params.
    store: Store
    storage_key: str
    request_identifier: str

    # bucket related params
    name: str
    capacity: int
    refill_rate: float
    tokens: float
    set_headers: bool
    set_429_headers: bool
    last_refill: float = field(default_factory=time.monotonic)

    async def allow_request(self) -> bool:
        """Attempt to consume one token from the bucket.

        Returns:
            bool: True if a token was consumed, False if no tokens were available.
        """
        now = time.monotonic()
        tokens_to_add = (now - self.last_refill) * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

        allowed = self.tokens >= 1
        if allowed:
            self.tokens -= 1

        await self.save()

        return allowed

    async def save(self) -> None:
        """Persist the current state of the bucket."""
        to_store = BucketState(self.tokens, self.last_refill)
        await self.store.set(self.storage_key, encode_json(to_store), expires_in=self.expires_in)

    @classmethod
    async def from_store_or_new(
        cls,
        *,
        store: Store,
        storage_key: str,
        request_identifier: str,
        limit_policy: RateLimitPolicy,
    ) -> Self:
        """Load a token bucket from the store, or create a new one.

        Args:
            store (Store): Backend store instance.
            storage_key (str): Unique key identifying the bucket.
            request_identifier (str): Unique identifier for the request.
            limit_policy (RateLimitPolicy): Rate limit policy specifying capacity and refill rate.

        Returns:
            TokenBucket: A restored or newly created token bucket instance.
        """
        kwargs: dict[str, Any] = {
            "store": store,
            "request_identifier": request_identifier,
            "storage_key": storage_key,
            "capacity": limit_policy.capacity,
            "refill_rate": limit_policy.refill_rate,
            "name": limit_policy.name,
            "set_headers": limit_policy.set_headers,
            "set_429_headers": limit_policy.set_429_headers,
        }
        cached = await store.get(storage_key)

        if cached is not None:
            stored = decode_json(cached, target_type=BucketState)
            kwargs["tokens"] = stored.tokens
            kwargs["last_refill"] = stored.last_refill
        else:
            kwargs["tokens"] = limit_policy.capacity

        return cls(**kwargs)

    def __gt__(self, other: TokenBucket) -> bool:
        """Compare two token buckets based on their tokens."""
        return self.tokens > other.tokens

    @property
    def expires_in(self) -> int:
        """Calculate the number of seconds until the bucket entry expires in the store.

        The expiration is calculated as the time required to fully refill the bucket, plus a grace period of one minute.

        Returns:
            int: Expiration time in seconds.
        """
        return math.ceil(self.capacity / self.refill_rate) + 60

    @property
    def reset_after(self) -> float:
        """Calculate the number of seconds until the next token becomes available.

        At least one token is required to accept a request. If the bucket already has one or more tokens, the reset time is zero. Otherwise, the time is calculated as the deficit divided by the refill rate.

        Returns:
            float: Time in seconds until the bucket has at least one token.
        """
        return max(0, 1 - self.tokens) / self.refill_rate

    def build_headers(self) -> dict[str, str]:
        """Build the headers for the response.

        Returns:
            dict[str, str]: The headers for the response.
        """
        # Calculate window: time to refill empty bucket to full capacity
        window = math.ceil(self.capacity / self.refill_rate)

        return {
            "RateLimit-Policy": f'"{self.name}";q={int(self.capacity)};w={window}',
            "RateLimit": f'"{self.name}";r={int(self.tokens)};t={math.ceil(self.reset_after)}',
        }


class RateLimitMiddleware(ASGIMiddleware):
    """Enforce token bucket-based rate limiting for both global and per-route limits.

    This middleware enforces both global and per-route rate limits using the token bucket algorithm. Limits are defined as :class:`RateLimitPolicy` objects and can be configured globally (applied to all requests) or on a per-route basis.
    """

    global_limits: list[RateLimitPolicy]
    route_limits_key: str

    def __init__(
        self,
        exclude_path_pattern: str | tuple[str, ...] | None = None,
        global_limits: list[RateLimitPolicy] | None = None,
        exclude_opt_key: str = EXCLUDE_FROM_RATE_LIMIT_KEY,
        route_limits_key: str = "rate_limits",
    ) -> None:
        self.scopes = (ScopeType.HTTP,)
        self.exclude_opt_key = exclude_opt_key
        self.exclude_path_pattern = exclude_path_pattern
        self.route_limits_key = route_limits_key

        if global_limits is not None:
            global_limits.sort()

        self.global_limits = global_limits or []
        self.identifier_for_request: str = None

    async def handle(self, scope: Scope, receive: Receive, send: Send, next_app: ASGIApp) -> None:
        """Handle ASGI call for rate limiting.

        Args:
            scope (Scope): The ASGI connection scope.
            receive (Receive): The ASGI receive function.
            send (Send): The ASGI send function.
            next_app (ASGIApp): The next ASGI application in the middleware stack to call.
        """
        app = scope["litestar_app"]
        request: Request[Any, Any, Any] = app.request_class(scope)

        # Exit early if rate limiting is disabled for this request.
        if request.headers.get(IGNORE_RATE_LIMIT_HEADER_KEY) == "true":
            await next_app(scope, receive, send)
            return

        store = app.stores.get(settings.stores.rate_limit_key)

        # Get customized rate limits for a specific route.
        route_handler = scope["route_handler"]
        route_limits: list[RateLimitPolicy] = route_handler.opt.get(self.route_limits_key, [])
        route_limits.sort()

        allowed_buckets: list[TokenBucket] = []
        for limit_policy in chain(self.global_limits, route_limits):
            bucket = await self._handle_limit(
                limit_policy=limit_policy, request=request, store=store
            )
            allowed_buckets.append(bucket)

        send = self._wrap_send(send, buckets=allowed_buckets)

        await next_app(scope, receive, send)

    async def _handle_limit(
        self, limit_policy: RateLimitPolicy, request: Request[Any, Any, Any], store: Store
    ) -> TokenBucket | None:
        """Handle the limit for a given request."""
        is_exempt = limit_policy.is_exempt
        if is_exempt is not None and await is_exempt(request):
            return None

        request_identifier = self._get_request_identifier(request)
        storage_key = f"{request_identifier}:{limit_policy.name}"
        bucket = await TokenBucket.from_store_or_new(
            store=store,
            storage_key=storage_key,
            request_identifier=request_identifier,
            limit_policy=limit_policy,
        )

        if not await bucket.allow_request():
            kwargs: dict[str, Any] = {}

            if limit_policy.set_429_headers:
                kwargs["headers"] = bucket.build_headers()

            detail = "You are being rate limited."
            raise TooManyRequestsError(
                detail=detail, retry_after=round_up(bucket.reset_after), **kwargs
            )

        return bucket

    def _get_request_identifier(self, request: Request[Any, Any, Any]) -> str:
        """Get the identifier for the request. This is a unique identifier for the request that is used to identify the request in the store.

        Args:
            request (Request): The request to get the identifier for.

        Returns:
            str: The identifier for the request.
        """
        api_key = request.headers.get(AUTH_HEADER_KEY, None)
        if api_key:
            encryption_key = (
                settings.rate_limit.encryption_key or settings.authentication_encryption_key
            )
            return hmac.new(
                key=encryption_key.encode(),
                msg=api_key.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).hexdigest()[:16]

        return (
            request.headers.get("X-Forwarded-For", None)
            or request.headers.get("x-forwarded-for", None)
            or request.headers.get("X-Real-IP", None)
            or request.headers.get("x-real-ip", None)
            or request.headers.get("CF-Connecting-IP", None)
            or request.headers.get("cf-connecting-ip", None)
            or getattr(request.client, "host", "anonymous")
        )

    def _wrap_send(self, send: Send, buckets: list[TokenBucket]) -> Send:
        async def send_wrapper(message: Message) -> None:
            headers_to_set: dict[str, str] = {"RateLimit-Policy": "", "RateLimit": ""}
            for bucket in buckets:
                if bucket.set_headers:
                    headers = bucket.build_headers()
                    headers_to_set["RateLimit-Policy"] += f", {headers['RateLimit-Policy']}"
                    headers_to_set["RateLimit"] += f", {headers['RateLimit']}"

            headers_to_set["RateLimit-Policy"] = headers_to_set["RateLimit-Policy"].lstrip(", ")
            headers_to_set["RateLimit"] = headers_to_set["RateLimit"].lstrip(", ")

            if headers_to_set["RateLimit-Policy"] == "":
                headers_to_set.pop("RateLimit-Policy")
            if headers_to_set["RateLimit"] == "":
                headers_to_set.pop("RateLimit")

            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                headers = MutableScopeHeaders(message)  # type: ignore [assignment]
                for k, v in headers_to_set.items():
                    headers[k] = v
            await send(message)

        return send_wrapper


rate_limit_middleware = RateLimitMiddleware(
    global_limits=[
        RateLimitPolicy(
            name=v.name,
            capacity=v.capacity,
            refill_rate=v.refill_rate,
            priority=v.priority,
            set_headers=v.set_headers,
            set_429_headers=v.set_429_headers,
        )
        for v in settings.rate_limit.policies.values()
    ],
)
