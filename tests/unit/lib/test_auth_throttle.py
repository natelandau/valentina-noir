"""Unit tests for failed-authentication throttling."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from litestar.stores.redis import RedisStore

from vapi.config import settings
from vapi.lib.auth_throttle import AUTH_FAILURE_LIMIT, AuthFailureThrottle
from vapi.lib.exceptions import TooManyRequestsError

pytestmark = pytest.mark.anyio


def _connection(redis: Any, host: str) -> SimpleNamespace:
    store = RedisStore(redis=redis, namespace=f"{settings.slug}:{settings.stores.rate_limit_key}")
    app = SimpleNamespace(stores=SimpleNamespace(get=lambda _name: store))
    return SimpleNamespace(app=app, client=SimpleNamespace(host=host))


async def test_blocks_client_after_too_many_failures(redis: Any) -> None:
    """Verify a client that keeps failing authentication is refused before the next check."""
    # Given a client that has failed authentication up to the limit
    throttle = AuthFailureThrottle(_connection(redis, "203.0.113.9"))
    for _ in range(AUTH_FAILURE_LIMIT):
        await throttle.record_failure()

    # When/Then the next attempt is refused
    with pytest.raises(TooManyRequestsError):
        await throttle.check()


async def test_failures_are_counted_per_client(redis: Any) -> None:
    """Verify one client's failures do not block another client."""
    # Given one client at the failure limit
    blocked = AuthFailureThrottle(_connection(redis, "203.0.113.9"))
    for _ in range(AUTH_FAILURE_LIMIT):
        await blocked.record_failure()

    # When/Then a different client is still allowed
    await AuthFailureThrottle(_connection(redis, "198.51.100.7")).check()
