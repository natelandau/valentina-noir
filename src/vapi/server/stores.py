"""Manage session storage."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from litestar.stores.redis import RedisStore as LitestarRedisStore

from vapi.config import settings

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import timedelta

    from redis.asyncio import Redis

    type SetManyItem = tuple[str, str | bytes, int | timedelta | None]

logger = logging.getLogger("vapi")


__all__ = ("RedisStore",)


class RedisStore(LitestarRedisStore):
    """Redis based, thread and process safe asynchronous key/value store.

    Extends :class:`litestar.stores.redis.RedisStore` to add additional
    functionality.
    """

    _redis: Redis[bytes]  # type: ignore [type-arg]

    async def set_many(self, items: Iterable[SetManyItem], *, transaction: bool = True) -> None:
        """Set multiple key-value pairs in Redis.

        Args:
            items (Iterable[SetManyItem]): An iterable of tuples containing ``(key, value, expires_in)``.
            transaction (bool): If ``True`` all items are set atomically (the default is True).
        """
        pipe = self._redis.pipeline(transaction=transaction)

        for key, value, expires_in in items:
            value_bytes = value.encode("utf-8") if isinstance(value, str) else value
            pipe.set(self._make_key(key), value_bytes, expires_in)

        await pipe.execute()

    async def delete_by_prefix(self, match: str) -> None:
        """Delete a value from the session storage by prefix.

        Args:
            match (str): The prefix to use for the session storage.
        """
        i = 0
        async for key in self._redis.scan_iter(match=f"{settings.slug}:{match}:*", count=500):
            await self._redis.delete(key)
            i += 1

        msg = f"Deleted {i} keys"
        logger.debug(msg, extra={"component": "cache"})
