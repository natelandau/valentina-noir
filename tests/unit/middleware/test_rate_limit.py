"""Unit tests for rate limit middleware."""

from __future__ import annotations

import hashlib
import hmac
import math
import time
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from litestar.serialization import decode_json, encode_json

from vapi.constants import AUTH_HEADER_KEY, IGNORE_RATE_LIMIT_HEADER_KEY
from vapi.lib.exceptions import TooManyRequestsError
from vapi.middleware.rate_limit import (
    BucketState,
    RateLimitMiddleware,
    RateLimitPolicy,
    TokenBucket,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(cached: bytes | None = None) -> AsyncMock:
    """Create a mock Store that optionally returns cached bucket state."""
    store = AsyncMock()
    store.get = AsyncMock(return_value=cached)
    store.set = AsyncMock()
    return store


def _make_policy(**overrides: Any) -> RateLimitPolicy:
    """Create a RateLimitPolicy with sensible defaults."""
    defaults: dict[str, Any] = {
        "name": "test",
        "capacity": 10,
        "refill_rate": 1.0,
    }
    defaults.update(overrides)
    return RateLimitPolicy(**defaults)


def _make_bucket(store: AsyncMock | None = None, **overrides: Any) -> TokenBucket:
    """Create a TokenBucket with sensible defaults."""
    defaults: dict[str, Any] = {
        "store": store or _make_store(),
        "storage_key": "key",
        "request_identifier": "user1",
        "name": "test",
        "capacity": 10,
        "refill_rate": 1.0,
        "tokens": 10.0,
        "set_headers": True,
        "set_429_headers": True,
    }
    defaults.update(overrides)
    return TokenBucket(**defaults)


def _make_request(
    headers: dict[str, str] | None = None,
    client_host: str | None = "127.0.0.1",
) -> MagicMock:
    """Create a mock Request with configurable headers and client."""
    _headers = headers or {}
    mock_request = MagicMock()
    mock_request.headers = MagicMock()
    mock_request.headers.get = lambda key, default=None: _headers.get(key, default)
    if client_host is None:
        mock_request.client = None
    else:
        mock_request.client = MagicMock()
        mock_request.client.host = client_host
    return mock_request


def _make_scope(
    *,
    route_handler_opt: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create a minimal ASGI HTTP scope for testing rate limit middleware."""
    mock_route_handler = MagicMock()
    mock_route_handler.opt = route_handler_opt or {}

    mock_app = MagicMock()
    mock_store = _make_store()
    mock_app.stores.get = MagicMock(return_value=mock_store)

    mock_request = _make_request(headers=headers)
    mock_request_cls = MagicMock(return_value=mock_request)
    mock_app.request_class = mock_request_cls

    return {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/test",
        "headers": [],
        "state": {},
        "route_handler": mock_route_handler,
        "litestar_app": mock_app,
    }


def _capturing_send() -> tuple[Any, list[dict[str, Any]]]:
    """Create a send callable that captures ASGI messages.

    Returns:
        tuple: (send_fn, sent_messages list).
    """
    sent_messages: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent_messages.append(message)

    return send, sent_messages


def _extract_header_names(message: dict[str, Any]) -> set[str]:
    """Extract decoded header names from an http.response.start message."""
    return {k.decode() if isinstance(k, bytes) else k for k, _ in message.get("headers", [])}


def _extract_headers(message: dict[str, Any]) -> dict[str, str]:
    """Extract decoded header key-value pairs from an http.response.start message."""
    result: dict[str, str] = {}
    for raw_key, raw_value in message.get("headers", []):
        key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
        value = raw_value.decode() if isinstance(raw_value, bytes) else raw_value
        result[key] = value
    return result


# ---------------------------------------------------------------------------
# TokenBucket
# ---------------------------------------------------------------------------


class TestTokenBucketAllowRequest:
    """Test token consumption and refill logic."""

    async def test_allow_request_consumes_token(self) -> None:
        """Verify a successful request consumes one token."""
        # Given a bucket with 5 tokens
        store = _make_store()
        bucket = _make_bucket(store=store, tokens=5.0)

        # When a request is allowed
        result = await bucket.allow_request()

        # Then one token is consumed
        assert result is True
        assert bucket.tokens < 5.0
        store.set.assert_awaited_once()

    async def test_deny_request_when_empty(self) -> None:
        """Verify request is denied when no tokens remain."""
        # Given a bucket with no tokens
        bucket = _make_bucket(tokens=0.0, last_refill=time.monotonic())

        # When a request is attempted
        result = await bucket.allow_request()

        # Then the request is denied
        assert result is False

    async def test_refill_adds_tokens_over_time(self) -> None:
        """Verify tokens are refilled based on elapsed time."""
        # Given a bucket emptied 5 seconds ago with refill_rate=2.0
        bucket = _make_bucket(
            tokens=0.0,
            refill_rate=2.0,
            last_refill=time.monotonic() - 5,
        )

        # When a request is attempted
        result = await bucket.allow_request()

        # Then the bucket refilled and the request is allowed
        assert result is True

    async def test_refill_capped_at_capacity(self) -> None:
        """Verify token refill does not exceed bucket capacity."""
        # Given a bucket that has been idle for a long time
        bucket = _make_bucket(
            tokens=0.0,
            capacity=10,
            refill_rate=100.0,
            last_refill=time.monotonic() - 1000,
        )

        # When a request is attempted
        await bucket.allow_request()

        # Then tokens do not exceed capacity (minus the 1 consumed)
        assert bucket.tokens <= 10


class TestTokenBucketPersistence:
    """Test store persistence and restoration."""

    async def test_save_persists_state(self) -> None:
        """Verify save writes BucketState to the store."""
        # Given a bucket with known state
        store = _make_store()
        bucket = _make_bucket(store=store, tokens=7.5)

        # When saving
        await bucket.save()

        # Then the store receives the serialized state
        store.set.assert_awaited_once()
        call_args = store.set.call_args
        stored = decode_json(call_args.args[1], target_type=BucketState)
        assert stored.tokens == 7.5

    async def test_from_store_restores_cached_bucket(self) -> None:
        """Verify bucket is restored from cached state."""
        # Given a cached bucket state
        cached_state = BucketState(tokens=3.0, last_refill=time.monotonic() - 1)
        store = _make_store(cached=encode_json(cached_state))
        policy = _make_policy()

        # When loading from store
        bucket = await TokenBucket.from_store_or_new(
            store=store,
            storage_key="key",
            request_identifier="user1",
            limit_policy=policy,
        )

        # Then the bucket has the cached token count
        assert bucket.tokens == 3.0

    async def test_from_store_creates_new_when_uncached(self) -> None:
        """Verify a full bucket is created when no cached state exists."""
        # Given no cached state
        store = _make_store(cached=None)
        policy = _make_policy(capacity=20)

        # When loading from store
        bucket = await TokenBucket.from_store_or_new(
            store=store,
            storage_key="key",
            request_identifier="user1",
            limit_policy=policy,
        )

        # Then the bucket starts at full capacity
        assert bucket.tokens == 20


class TestTokenBucketProperties:
    """Test computed properties and header building."""

    def test_expires_in_includes_grace_period(self) -> None:
        """Verify expiration is refill time plus 60 seconds."""
        # Given a bucket with capacity=100 and refill_rate=10
        bucket = _make_bucket(capacity=100, refill_rate=10.0)

        # Then expires_in is ceil(100/10) + 60 = 70
        assert bucket.expires_in == 70

    def test_reset_after_zero_when_tokens_available(self) -> None:
        """Verify reset_after is 0 when at least one token is available."""
        # Given a bucket with tokens
        bucket = _make_bucket(tokens=5.0)

        # Then reset_after is 0
        assert bucket.reset_after == 0

    def test_reset_after_positive_when_empty(self) -> None:
        """Verify reset_after reflects time to get one token when empty."""
        # Given an empty bucket with refill_rate=2
        bucket = _make_bucket(tokens=0.0, refill_rate=2.0)

        # Then reset_after is 1/2 = 0.5
        assert bucket.reset_after == 0.5

    def test_build_headers_format(self) -> None:
        """Verify headers follow the IETF rate limit header format."""
        # Given a bucket with known state
        bucket = _make_bucket(
            name="api",
            capacity=100,
            refill_rate=10.0,
            tokens=50.0,
        )

        # When building headers
        headers = bucket.build_headers()

        # Then headers match IETF format
        window = math.ceil(100 / 10.0)
        assert headers["RateLimit-Policy"] == f'"api";q=100;w={window}'
        assert headers["RateLimit"] == f'"api";r=50;t={math.ceil(bucket.reset_after)}'


# ---------------------------------------------------------------------------
# RateLimitPolicy
# ---------------------------------------------------------------------------


class TestRateLimitPolicyOrdering:
    """Test policy sorting behavior."""

    def test_policies_sort_by_priority(self) -> None:
        """Verify policies sort so higher priority values come first."""
        # Given policies with different priorities
        policies = [
            _make_policy(name="low", priority=10),
            _make_policy(name="high", priority=1),
            _make_policy(name="mid", priority=5),
        ]

        # When sorted
        policies.sort()

        # Then higher-priority-number policies appear first (inverted __gt__)
        names = [p.name for p in policies]
        assert names == ["low", "mid", "high"]


# ---------------------------------------------------------------------------
# RateLimitMiddleware._get_request_identifier
# ---------------------------------------------------------------------------


class TestGetRequestIdentifier:
    """Test request identifier extraction."""

    def test_identifier_from_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify HMAC-based identifier is returned when API key is present."""
        # Given a request with an API key header
        from vapi.config import settings

        monkeypatch.setattr(settings.rate_limit, "encryption_key", "test-key")

        middleware = RateLimitMiddleware.__new__(RateLimitMiddleware)
        api_key = "my-api-key"
        mock_request = _make_request(headers={AUTH_HEADER_KEY: api_key})

        # When getting the identifier
        result = middleware._get_request_identifier(mock_request)

        # Then it returns a truncated HMAC hex digest
        expected = hmac.new(
            key=b"test-key",
            msg=api_key.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()[:16]
        assert result == expected

    @pytest.mark.parametrize(
        ("headers", "client_host", "expected"),
        [
            ({"X-Forwarded-For": "203.0.113.1"}, "10.0.0.1", "203.0.113.1"),
            ({}, "10.0.0.1", "10.0.0.1"),
            ({}, None, "anonymous"),
        ],
        ids=["forwarded-ip", "client-host", "anonymous"],
    )
    def test_identifier_fallback_chain(
        self, headers: dict[str, str], client_host: str | None, expected: str
    ) -> None:
        """Verify identifier falls back through proxy headers, client host, then anonymous."""
        # Given a request with the specified headers and client
        middleware = RateLimitMiddleware.__new__(RateLimitMiddleware)
        mock_request = _make_request(headers=headers, client_host=client_host)

        # When getting the identifier
        result = middleware._get_request_identifier(mock_request)

        # Then the expected identifier is returned
        assert result == expected


# ---------------------------------------------------------------------------
# RateLimitMiddleware._wrap_send
# ---------------------------------------------------------------------------


class TestWrapSend:
    """Test response header injection."""

    async def test_headers_set_on_response_start(self) -> None:
        """Verify rate limit headers are injected into http.response.start."""
        # Given a middleware with one bucket that has headers enabled
        middleware = RateLimitMiddleware.__new__(RateLimitMiddleware)
        bucket = _make_bucket(name="api", capacity=100, refill_rate=10.0, tokens=50.0)
        send, sent_messages = _capturing_send()

        # When wrapping send and sending a response
        wrapped = middleware._wrap_send(send, buckets=[bucket])
        await wrapped({"type": "http.response.start", "status": 200, "headers": []})
        await wrapped({"type": "http.response.body", "body": b"ok"})

        # Then rate limit headers are present on the start message
        header_names = _extract_header_names(sent_messages[0])
        assert "ratelimit-policy" in header_names
        assert "ratelimit" in header_names

    async def test_none_buckets_are_skipped(self) -> None:
        """Verify None buckets from exempt policies are handled gracefully."""
        # Given a middleware with a mix of real and None buckets
        middleware = RateLimitMiddleware.__new__(RateLimitMiddleware)
        bucket = _make_bucket(name="api", tokens=5.0)
        send, sent_messages = _capturing_send()

        # When wrapping send with a None bucket
        wrapped = middleware._wrap_send(send, buckets=[None, bucket])
        await wrapped({"type": "http.response.start", "status": 200, "headers": []})

        # Then no error occurs and headers from the real bucket are present
        assert "ratelimit-policy" in _extract_header_names(sent_messages[0])

    async def test_no_headers_when_all_buckets_hidden(self) -> None:
        """Verify no rate limit headers when all buckets have set_headers=False."""
        # Given a bucket with headers disabled
        middleware = RateLimitMiddleware.__new__(RateLimitMiddleware)
        bucket = _make_bucket(set_headers=False)
        send, sent_messages = _capturing_send()

        # When wrapping send
        wrapped = middleware._wrap_send(send, buckets=[bucket])
        await wrapped({"type": "http.response.start", "status": 200, "headers": []})

        # Then no rate limit headers are added
        header_names = _extract_header_names(sent_messages[0])
        assert "ratelimit-policy" not in header_names
        assert "ratelimit" not in header_names

    async def test_body_messages_pass_through_unchanged(self) -> None:
        """Verify non-response-start messages are not modified."""
        # Given a middleware with a bucket
        middleware = RateLimitMiddleware.__new__(RateLimitMiddleware)
        bucket = _make_bucket()
        send, sent_messages = _capturing_send()

        # When sending a body message
        wrapped = middleware._wrap_send(send, buckets=[bucket])
        await wrapped({"type": "http.response.body", "body": b"hello"})

        # Then the message is forwarded unchanged
        assert sent_messages[0]["body"] == b"hello"


# ---------------------------------------------------------------------------
# RateLimitMiddleware.handle
# ---------------------------------------------------------------------------


class TestRateLimitMiddlewareHandle:
    """Test the full middleware handle flow."""

    async def test_bypass_when_ignore_header_present(self) -> None:
        """Verify rate limiting is skipped when the ignore header is set."""
        # Given a scope with the ignore header
        scope = _make_scope(headers={IGNORE_RATE_LIMIT_HEADER_KEY: "true"})

        middleware = RateLimitMiddleware(global_limits=[])
        next_app = AsyncMock()

        # When the middleware handles the request
        await middleware.handle(scope, AsyncMock(), AsyncMock(), next_app)

        # Then the next app is called without rate limiting
        next_app.assert_awaited_once()

    async def test_raises_too_many_requests_when_bucket_empty(self, mocker: MockerFixture) -> None:
        """Verify TooManyRequestsError is raised when rate limit is exceeded."""
        # Given a policy with 0 capacity (immediately exceeded)
        policy = _make_policy(capacity=0, refill_rate=1.0)
        scope = _make_scope()

        # Given TokenBucket.from_store_or_new returns an empty bucket
        empty_bucket = _make_bucket(tokens=0.0, capacity=0, last_refill=time.monotonic())
        mocker.patch(
            "vapi.middleware.rate_limit.TokenBucket.from_store_or_new",
            new_callable=AsyncMock,
            return_value=empty_bucket,
        )

        middleware = RateLimitMiddleware(global_limits=[policy])

        # When the middleware handles the request
        # Then TooManyRequestsError is raised
        with pytest.raises(TooManyRequestsError):
            await middleware.handle(scope, AsyncMock(), AsyncMock(), AsyncMock())

    async def test_exempt_policy_returns_none_bucket(self) -> None:
        """Verify exempt policies produce None buckets without consuming tokens."""

        # Given a policy where all requests are exempt
        async def always_exempt(_request: Any) -> bool:
            return True

        policy = _make_policy(is_exempt=always_exempt)
        scope = _make_scope()

        middleware = RateLimitMiddleware(global_limits=[policy])
        next_app = AsyncMock()

        # When the middleware handles the request
        await middleware.handle(scope, AsyncMock(), AsyncMock(), next_app)

        # Then next_app is called (no rate limit error)
        next_app.assert_awaited_once()

    async def test_multiple_policies_headers_combined(self, mocker: MockerFixture) -> None:
        """Verify headers from multiple policies are combined with commas."""
        # Given two policies
        policy_a = _make_policy(name="global", capacity=100, refill_rate=10.0)
        policy_b = _make_policy(name="route", capacity=10, refill_rate=1.0)

        scope = _make_scope(route_handler_opt={"rate_limits": [policy_b]})

        # Given TokenBucket.from_store_or_new returns full buckets
        call_count = 0

        async def mock_from_store(
            *, store: Any, storage_key: str, request_identifier: str, limit_policy: RateLimitPolicy
        ) -> TokenBucket:
            nonlocal call_count
            call_count += 1
            return _make_bucket(
                store=store,
                name=limit_policy.name,
                capacity=limit_policy.capacity,
                refill_rate=limit_policy.refill_rate,
                tokens=float(limit_policy.capacity),
            )

        mocker.patch(
            "vapi.middleware.rate_limit.TokenBucket.from_store_or_new",
            side_effect=mock_from_store,
        )

        send, sent_messages = _capturing_send()

        async def mock_next_app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = RateLimitMiddleware(global_limits=[policy_a])

        # When the middleware handles the request
        await middleware.handle(scope, AsyncMock(), send, mock_next_app)

        # Then both policies were evaluated
        assert call_count == 2

        # Then response headers contain both policies
        start_msg = next(m for m in sent_messages if m["type"] == "http.response.start")
        headers_dict = _extract_headers(start_msg)
        assert "global" in headers_dict.get("ratelimit-policy", "")
        assert "route" in headers_dict.get("ratelimit-policy", "")
