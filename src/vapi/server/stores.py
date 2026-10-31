"""Manage session storage."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from litestar.stores.redis import RedisStore as LitestarRedisStore

from vapi.config import settings
from vapi.domain.urls import Companies

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import timedelta

    from redis.asyncio import Redis

    type SetManyItem = tuple[str, str | bytes, int | timedelta | None]

logger = logging.getLogger("vapi")


__all__ = ("RedisStore",)

_COMPANY_PATH = re.compile(r"/companies/([0-9a-fA-F-]{36})")
# The company list key is the method, path, and query string with no separator,
# so the list is the company path not followed by a slash
_COMPANY_LIST_PATH = re.compile(rf":GET{re.escape(Companies.LIST)}(?!/)")


class RedisStore(LitestarRedisStore):
    """Redis based, thread and process safe asynchronous key/value store.

    Extends :class:`litestar.stores.redis.RedisStore` to add additional
    functionality.
    """

    _redis: Redis

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

    async def set_if_absent(self, key: str, value: str | bytes, *, expires_in: int) -> bool:
        """Set a value only if the key does not exist, atomically (Redis ``SET NX``).

        Use to claim a key across concurrent requests or processes: exactly one caller wins.

        Args:
            key (str): Key to claim.
            value (str | bytes): Value to store.
            expires_in (int): Seconds before the key expires.

        Returns:
            bool: True if this call set the key, False if it already existed.
        """
        return bool(await self._redis.set(self._make_key(key), value, ex=expires_in, nx=True))

    async def set(
        self, key: str, value: str | bytes, expires_in: int | timedelta | None = None
    ) -> None:
        """Set a value, and index response-cache entries by developer and company.

        The indexes let a write delete exactly the affected cached responses instead of
        scanning the whole keyspace.

        Args:
            key (str): Key to associate the value with.
            value (str | bytes): Value to store.
            expires_in (int | timedelta | None): Time in seconds before the key is considered expired.
        """
        await super().set(key, value, expires_in)
        if self.namespace != f"{settings.slug}:{settings.stores.response_cache_key}":
            return

        # Response-cache keys start with the API key fingerprint (see response_cache_key_builder)
        index_keys = [_index_key("developer", key.split(":", 1)[0])]
        if company := _COMPANY_PATH.search(key):
            index_keys.append(_index_key("company", company.group(1)))
        elif _COMPANY_LIST_PATH.search(key):
            # Company lists embed every listed company's data and counts, so any
            # company write must be able to clear every developer's cached list
            index_keys.append(_index_key("company_list", "all"))

        ttl = expires_in if expires_in is not None else settings.stores.ttl
        pipe = self._redis.pipeline(transaction=False)
        for index_key in index_keys:
            pipe.sadd(index_key, self._make_key(key))
            pipe.expire(index_key, ttl)
        await pipe.execute()

    async def delete_indexed(self, kind: str, value: str) -> None:
        """Delete every response-cache entry indexed under one developer or company.

        Args:
            kind (str): ``developer`` (an API key fingerprint), ``company`` (a company ID,
                in any letter case), or ``company_list`` (``all``, every cached company list).
            value (str): The fingerprint, company ID, or ``all``.
        """
        index_key = _index_key(kind, value)
        members = await self._redis.smembers(index_key)  # ty:ignore[invalid-await]
        await self._redis.unlink(index_key, *members)


def _index_key(kind: str, value: str) -> str:
    # UUIDs are case-insensitive in paths, so index every spelling of a company ID together
    if kind == "company":
        value = value.lower()
    return f"{settings.slug}:{settings.stores.response_cache_key}_index:{kind}:{value}"
