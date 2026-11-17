"""Manage session storage."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from litestar.stores.redis import RedisStore as LitestarRedisStore

from vapi.config import settings
from vapi.domain.urls import Companies
from vapi.lib.stores import split_caller_key

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import timedelta

    from redis.asyncio import Redis

    type SetManyItem = tuple[str, str | bytes, int | timedelta | None]

logger = logging.getLogger("vapi")


__all__ = ("RedisStore",)

# Company routes take any spelling ``UUID()`` parses, so match the whole segment and canonicalize it
_COMPANY_PATH = re.compile(r"/companies/([^/?]+)")
# The company list key is the method and path, then a query string after "?" if any,
# so the list is the company path not followed by a slash
_COMPANY_LIST_PATH = re.compile(rf"GET{re.escape(Companies.LIST)}(?!/)")


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

        ttl = expires_in if expires_in is not None else settings.stores.ttl
        pipe = self._redis.pipeline(transaction=False)
        for index_key in _index_keys_for(key):
            pipe.sadd(index_key, self._make_key(key))
            # Only ever extend the index's life, so it outlives its longest-lived entry
            pipe.expire(index_key, ttl, nx=True)
            pipe.expire(index_key, ttl, gt=True)
        await pipe.execute()

    async def generations(self, key: str) -> list[bytes | None]:
        """Read the flush generation of every index a response-cache key belongs to.

        Read before a handler queries the database and again after its response is
        cached. A difference means a flush ran in between, so the cached response may
        predate the write that triggered it.

        Args:
            key (str): The response-cache key.

        Returns:
            list[bytes | None]: One generation per index, None where none was flushed recently.
        """
        return await self._redis.mget([_generation_key(i) for i in _index_keys_for(key)])

    async def delete_indexed(self, kind: str, value: str) -> None:
        """Delete every response-cache entry indexed under one developer or company.

        Args:
            kind (str): ``developer`` (an API key fingerprint), ``company`` (a company ID,
                in any spelling ``UUID()`` accepts), or ``company_list`` (``all``, every cached company list).
            value (str): The fingerprint, company ID, or ``all``.
        """
        index_key = _index_key(kind, value)
        # Bump the generation before deleting so a request that read the database before
        # this flush sees the change and drops the response it cached afterward.
        pipe = self._redis.pipeline(transaction=False)
        pipe.set(_generation_key(index_key), uuid4().hex, ex=settings.stores.generation_ttl)
        pipe.smembers(index_key)
        _, members = await pipe.execute()
        await self._redis.unlink(index_key, *members)


def _index_keys_for(key: str) -> list[str]:
    """Return the indexes a response-cache key belongs to."""
    fingerprint, request_line = split_caller_key(key)

    index_keys = [_index_key("developer", fingerprint)]
    if company := _COMPANY_PATH.search(request_line):
        index_keys.append(_index_key("company", company.group(1)))
    elif _COMPANY_LIST_PATH.match(request_line):
        # Company lists embed every listed company's data and counts, so any
        # company write must be able to clear every developer's cached list
        index_keys.append(_index_key("company_list", "all"))
    return index_keys


def _index_key(kind: str, value: str) -> str:
    # Company routes accept every spelling UUID() parses, so index them all under one ID
    if kind == "company":
        try:
            value = str(UUID(value))
        except ValueError:
            value = value.lower()
    return f"{settings.slug}:{settings.stores.response_cache_key}_index:{kind}:{value}"


def _generation_key(index_key: str) -> str:
    # A separate prefix keeps a generation key from ever equaling an index key, since a
    # company path segment may itself end in ":generation"
    return f"{settings.slug}:{settings.stores.response_cache_key}_generation:{index_key}"
