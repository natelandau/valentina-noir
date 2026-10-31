"""Unit tests for idempotency middleware scope-state and response-caching behavior."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from litestar import Litestar, Request, Response, post
from litestar.stores.registry import StoreRegistry
from litestar.testing import TestClient

from vapi.constants import (
    IDEMPOTENCY_KEY_HEADER,
    IDEMPOTENCY_KEY_MAX_LENGTH,
    IDEMPOTENCY_KEY_STATE_KEY,
    IDEMPOTENCY_MAX_CACHED_BODY_BYTES,
    SENSITIVE_RESPONSE_OPT_KEY,
)
from vapi.domain.controllers.developer.controllers import DeveloperController
from vapi.domain.controllers.global_admin.controllers import GlobalAdminController
from vapi.lib.exceptions import HTTPError, http_error_to_http_response
from vapi.middleware.idempotency import (
    IN_PROGRESS_DETAIL,
    IdempotencyMiddleware,
    ResponseCapture,
    _release_in_flight,
    idempotency_middleware,
)
from vapi.server.stores import RedisStore

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture


@post("/thing")
async def _create(data: dict, request: Request) -> dict:
    """Echo back whatever idempotency key the middleware stashed on scope state."""
    return {"stashed": request.scope["state"].get(IDEMPOTENCY_KEY_STATE_KEY)}


def _build_app() -> Litestar:
    return Litestar(route_handlers=[_create], middleware=[idempotency_middleware])


def _build_counter_app(*, sensitive: bool) -> Litestar:
    calls = {"count": 0}

    @post("/mint", opt={SENSITIVE_RESPONSE_OPT_KEY: sensitive})
    async def _mint(data: dict) -> dict:
        """Return a value that changes on every handler run."""
        calls["count"] += 1
        return {"secret": f"key-{calls['count']}"}

    return Litestar(route_handlers=[_mint], middleware=[idempotency_middleware])


@pytest.mark.parametrize(
    ("sensitive", "expected_second"),
    [(False, "key-1"), (True, "key-2")],
    ids=["normal_route_replays", "sensitive_route_not_cached"],
)
def test_sensitive_route_response_is_never_replayed(
    sensitive: bool,
    expected_second: str,
) -> None:
    """Verify a route flagged as sensitive is never cached, so a repeat key runs the handler again."""
    # Given a route whose response changes on every call
    app = _build_counter_app(sensitive=sensitive)

    # When the same Idempotency-Key and body are sent twice
    with TestClient(app=app) as client:
        headers = {IDEMPOTENCY_KEY_HEADER: "idem-mint"}
        client.post("/mint", json={"x": 1}, headers=headers)
        second = client.post("/mint", json={"x": 1}, headers=headers)

    # Then only the unflagged route replays the first response
    assert second.json()["secret"] == expected_second


@pytest.mark.parametrize(
    "route_handler",
    [DeveloperController.new_api_key, GlobalAdminController.new_api_key],
    ids=["developer_me", "global_admin"],
)
def test_api_key_routes_are_flagged_sensitive(route_handler: object) -> None:
    """Verify every route that returns a new API key carries the sensitive-response flag."""
    # Given a route that mints an API key
    # When reading its opt mapping
    opt = getattr(route_handler, "opt", {})

    # Then the sensitive-response flag is set
    assert opt.get(SENSITIVE_RESPONSE_OPT_KEY) is True


def test_idempotency_key_stashed_on_scope_state() -> None:
    """Verify the idempotency key is written to scope state for downstream logging."""
    # Given an app with the idempotency middleware and a route that reads scope state
    app = _build_app()

    # When a POST carries an Idempotency-Key header
    with TestClient(app=app) as client:
        response = client.post("/thing", json={"x": 1}, headers={IDEMPOTENCY_KEY_HEADER: "idem-1"})

    # Then the key is present on scope state during handler execution
    assert response.json()["stashed"] == "idem-1"


def test_idempotency_key_absent_when_header_missing() -> None:
    """Verify scope state has no idempotency key when the header is absent."""
    # Given an app with the idempotency middleware
    app = _build_app()

    # When a POST carries no Idempotency-Key header
    with TestClient(app=app) as client:
        response = client.post("/thing", json={"x": 1})

    # Then no idempotency key is stashed
    assert response.json()["stashed"] is None


@pytest.mark.anyio
class TestResponseCaptureCaching:
    """Tests for ResponseCapture._cache_response write/skip decisions."""

    @staticmethod
    def _build_capture(
        mocker: MockerFixture, *, status_code: int, body_parts: list[bytes]
    ) -> tuple[ResponseCapture, MagicMock]:
        """Build a ResponseCapture with a mocked store and the given captured state."""
        store = mocker.MagicMock()
        store.set = mocker.AsyncMock()
        capture = ResponseCapture(
            send=mocker.AsyncMock(),
            store=store,
            cache_key="idem-key",
            request_body_hash="body-hash",
        )
        capture._status_code = status_code
        capture._raw_headers = [(b"content-type", b"application/json")]
        capture._body_parts = body_parts
        return capture, store

    @pytest.mark.parametrize(
        ("status_code", "body_parts"),
        [
            (400, [b"bad request"]),
            (200, [b"x" * (IDEMPOTENCY_MAX_CACHED_BODY_BYTES + 1)]),
        ],
        ids=["non_2xx", "oversized"],
    )
    async def test_skips_caching(
        self, status_code: int, body_parts: list[bytes], mocker: MockerFixture
    ) -> None:
        """Verify non-2xx and oversized responses are not written to the cache."""
        # Given a captured response that must not be cached (bad status or too large)
        capture, store = self._build_capture(mocker, status_code=status_code, body_parts=body_parts)

        # When the response is finalized
        await capture._cache_response()

        # Then nothing is written to the store
        store.set.assert_not_called()

    async def test_caches_small_2xx_response(self, mocker: MockerFixture) -> None:
        """Verify a small 2xx response is written to the store."""
        # Given a small 2xx JSON response
        capture, store = self._build_capture(mocker, status_code=200, body_parts=[b'{"ok": true}'])

        # When the response is finalized
        await capture._cache_response()

        # Then it is written to the store exactly once
        store.set.assert_awaited_once()


def test_cache_key_separates_acting_users_and_query_strings() -> None:
    """Verify the replay key differs per On-Behalf-Of user and per query string."""

    # Given requests that differ only in acting user or query string
    def _request(path: str, on_behalf_of: str) -> Request:
        scope = {
            "type": "http",
            "method": "POST",
            "path": path.split("?", maxsplit=1)[0],
            "query_string": path.partition("?")[2].encode(),
            "headers": [(b"x-api-key", b"key"), (b"on-behalf-of", on_behalf_of.encode())],
        }
        return Request(scope)

    middleware = IdempotencyMiddleware()

    def _key(path: str, on_behalf_of: str) -> str:
        return middleware._build_cache_key(
            _request(path, on_behalf_of), idempotency_key="k", method="POST"
        )

    # When building cache keys / Then each difference yields a distinct key
    assert _key("/thing", "user-a") != _key("/thing", "user-b")
    assert _key("/thing?a=1", "user-a") != _key("/thing?a=2", "user-a")


class TestInFlightMarker:
    """Tests for refusing a duplicate while the first request with its key is running."""

    @staticmethod
    def _build_blocking_app(
        redis: Any, *, entered: asyncio.Event, release: asyncio.Event, status: list[int]
    ) -> Litestar:
        """Build an app on the Redis store whose handler waits for release before answering."""
        calls = {"count": 0}

        @post("/slow")
        async def _slow(data: dict) -> Response[dict]:
            calls["count"] += 1
            entered.set()
            await release.wait()
            return Response({"call": calls["count"]}, status_code=status[0])

        return Litestar(
            route_handlers=[_slow],
            middleware=[idempotency_middleware],
            exception_handlers={HTTPError: http_error_to_http_response},
            stores=StoreRegistry(
                default_factory=lambda name: RedisStore(redis, namespace=f"test-inflight:{name}")
            ),
        )

    @staticmethod
    def _client(app: Litestar) -> httpx.AsyncClient:
        """Return a client that runs the app in the test's event loop."""
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def test_duplicate_while_in_flight_is_refused_then_replayed(self, redis: Any) -> None:
        """Verify a duplicate during the first request gets 409, and one after it replays."""
        # Given a request with an idempotency key that is still running
        entered, release = asyncio.Event(), asyncio.Event()
        app = self._build_blocking_app(redis, entered=entered, release=release, status=[201])
        headers = {IDEMPOTENCY_KEY_HEADER: "idem-slow"}
        async with self._client(app) as client:
            first = asyncio.create_task(client.post("/slow", json={"x": 1}, headers=headers))
            await asyncio.wait_for(entered.wait(), timeout=5)

            # When a duplicate arrives before it finishes, and another after it finishes
            duplicate = await client.post("/slow", json={"x": 1}, headers=headers)
            release.set()
            first_response = await asyncio.wait_for(first, timeout=5)
            replay = await client.post("/slow", json={"x": 1}, headers=headers)

        # Then the duplicate is refused, the first succeeds, the later one replays it,
        # and the marker is gone
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == IN_PROGRESS_DETAIL
        assert first_response.status_code == 201
        assert replay.json() == first_response.json() == {"call": 1}
        assert not await redis.keys("test-inflight:*in_flight:*")

    async def test_marker_removed_after_failed_request(self, redis: Any) -> None:
        """Verify a failed request releases its key so a retry runs the handler again."""
        # Given a handler that fails on its first run
        entered, release = asyncio.Event(), asyncio.Event()
        release.set()
        status = [500]
        app = self._build_blocking_app(redis, entered=entered, release=release, status=status)
        headers = {IDEMPOTENCY_KEY_HEADER: "idem-fail"}

        # When the request fails and is retried after the server recovers
        async with self._client(app) as client:
            failed = await client.post("/slow", json={"x": 1}, headers=headers)
            status[0] = 201
            retry = await client.post("/slow", json={"x": 1}, headers=headers)

        # Then the retry runs the handler instead of getting 409
        assert failed.status_code == 500
        assert retry.status_code == 201
        assert retry.json() == {"call": 2}


async def test_redis_store_set_if_absent_claims_once(redis: Any) -> None:
    """Verify only the first set_if_absent call on a key succeeds."""
    # Given a Redis-backed store
    store = RedisStore(redis, namespace="test-set-if-absent")

    # When the same key is claimed twice
    first = await store.set_if_absent("k", b"1", expires_in=60)
    second = await store.set_if_absent("k", b"2", expires_in=60)

    # Then only the first claim wins and its value is kept, with an expiry
    assert (first, second) == (True, False)
    assert await store.get("k") == b"1"
    assert 0 < await store.expires_in("k") <= 60


def _build_validating_app() -> Litestar:
    return Litestar(
        route_handlers=[_create],
        middleware=[idempotency_middleware],
        exception_handlers={HTTPError: http_error_to_http_response},
    )


@pytest.mark.parametrize(
    "bad_key",
    ["k" * (IDEMPOTENCY_KEY_MAX_LENGTH + 1), "has space", "tab\there", "café"],
    ids=["too_long", "space", "control_char", "non_ascii"],
)
def test_invalid_idempotency_key_is_rejected(bad_key: str) -> None:
    """Verify an over-long or non-visible-ASCII Idempotency-Key is refused with a 400."""
    # Given an app with the idempotency middleware
    app = _build_validating_app()

    # When a request carries an invalid key
    with TestClient(app=app) as client:
        response = client.post(
            "/thing",
            json={},
            headers=[(IDEMPOTENCY_KEY_HEADER.encode(), bad_key.encode("latin-1"))],
        )

    # Then the request is refused and the error names the header
    assert response.status_code == 400
    assert response.json()["invalid_parameters"][0]["field"] == IDEMPOTENCY_KEY_HEADER


def test_max_length_visible_ascii_idempotency_key_is_accepted() -> None:
    """Verify a 255-character key of visible ASCII is accepted."""
    # Given a key at the length limit using punctuation and letters
    key = ("Ab9-_.~!" * 40)[:IDEMPOTENCY_KEY_MAX_LENGTH]

    # When it is sent
    with TestClient(app=_build_validating_app()) as client:
        response = client.post("/thing", json={}, headers={IDEMPOTENCY_KEY_HEADER: key})

    # Then the request succeeds and the key is stashed
    assert response.status_code == 201
    assert response.json() == {"stashed": key}


def test_replay_reruns_route_guards() -> None:
    """Verify a cached response is not replayed once a route guard starts refusing the caller."""
    # Given a route whose guard can be switched to refuse after the first request
    allowed = {"value": True}

    def _guard(_connection: object, _handler: object) -> None:
        if not allowed["value"]:
            raise HTTPError(status_code=403, detail="No rights to access this resource")

    @post("/guarded", guards=[_guard])
    async def _guarded(data: dict) -> dict:
        """Echo the request body."""
        return data

    app = Litestar(
        route_handlers=[_guarded],
        middleware=[idempotency_middleware],
        exception_handlers={HTTPError: http_error_to_http_response},
    )
    headers = {IDEMPOTENCY_KEY_HEADER: "guarded-key"}

    # When the first request succeeds and the guard refuses the duplicate
    with TestClient(app) as client:
        first = client.post("/guarded", json={"x": 1}, headers=headers)
        allowed["value"] = False
        replay = client.post("/guarded", json={"x": 1}, headers=headers)

    # Then the replay is refused like a live request
    assert first.status_code == 201
    assert replay.status_code == 403


async def test_release_in_flight_keeps_a_marker_claimed_by_another_request(redis: Any) -> None:
    """Verify releasing an in-flight marker leaves it alone once another request holds it."""
    # Given a marker now held by a later request after this request's claim lapsed
    store = RedisStore(redis, namespace="test-release-in-flight")
    await store.set("in_flight:k", b"later-token", expires_in=60)

    # When the earlier request releases with its own token
    await _release_in_flight(store=store, key="in_flight:k", token=b"earlier-token")

    # Then the later request's marker survives
    assert await store.get("in_flight:k") == b"later-token"
