"""Throttle repeated failed authentication attempts per client address."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from litestar.stores.redis import RedisStore

from vapi.config import settings
from vapi.lib.exceptions import TooManyRequestsError

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection

__all__ = ("AUTH_FAILURE_LIMIT", "AUTH_FAILURE_WINDOW_SECONDS", "AuthFailureThrottle")

logger = logging.getLogger("vapi")

AUTH_FAILURE_LIMIT = 20
AUTH_FAILURE_WINDOW_SECONDS = 300


class AuthFailureThrottle:
    """Count failed credential attempts per client address and refuse guessing past a limit.

    Authentication middleware runs before the rate limiter, so without this a caller could
    try API keys or Basic-auth passwords without limit. Only failures count, so clients
    with valid credentials are never slowed.
    """

    def __init__(self, connection: ASGIConnection) -> None:
        self._connection = connection

    @property
    def _key(self) -> str:
        host = getattr(self._connection.client, "host", None) or "unknown"
        return f"{settings.slug}:auth_failures:{host}"

    @property
    def _store(self) -> RedisStore | None:
        store = self._connection.app.stores.get(settings.stores.rate_limit_key)
        return store if isinstance(store, RedisStore) else None

    async def check(self) -> None:
        """Refuse the request when this client has failed too often within the window.

        Raises:
            TooManyRequestsError: If the client reached the failure limit.
        """
        store = self._store
        if store is None:
            return

        failures = await store._redis.get(self._key)  # noqa: SLF001
        if failures is not None and int(failures) >= AUTH_FAILURE_LIMIT:
            retry_after = await store._redis.ttl(self._key)  # noqa: SLF001
            raise TooManyRequestsError(
                detail="Too many failed authentication attempts",
                retry_after=max(int(retry_after), 1),
            )

    async def record_failure(self) -> None:
        """Count one failed attempt, starting the window on the first failure."""
        store = self._store
        if store is None:
            return

        pipe = store._redis.pipeline()  # noqa: SLF001
        pipe.incr(self._key)
        pipe.expire(self._key, AUTH_FAILURE_WINDOW_SECONDS, nx=True)
        await pipe.execute()
