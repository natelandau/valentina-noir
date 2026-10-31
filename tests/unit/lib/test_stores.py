"""Tests for the authentication cache helpers."""

from types import SimpleNamespace
from typing import Any

import pytest
from litestar.stores.memory import MemoryStore

from vapi.lib.stores import (
    cache_authenticated_developer,
    delete_authentication_cache_for_developer,
    get_authentication_generation,
)

pytestmark = pytest.mark.anyio

FINGERPRINT = "fingerprint-abc"


def _app_with_store(store: MemoryStore) -> Any:
    """Return a stand-in app whose store registry always yields the given store."""
    return SimpleNamespace(stores=SimpleNamespace(get=lambda _name: store))


async def test_cache_authenticated_developer_writes_when_not_evicted() -> None:
    """Verify a cache miss caches the developer when no eviction happened."""
    # Given a generation read before the database lookup, with no eviction afterward
    store = MemoryStore()
    generation = await get_authentication_generation(store=store, fingerprint=FINGERPRINT)

    # When the developer is cached
    await cache_authenticated_developer(
        store=store, fingerprint=FINGERPRINT, value=b"fresh", generation=generation
    )

    # Then the entry is stored
    assert await store.get(FINGERPRINT) == b"fresh"


async def test_cache_authenticated_developer_drops_stale_write_after_eviction() -> None:
    """Verify a cache miss that read the developer before an eviction does not re-cache it."""
    # Given a request that read the generation and the developer row before an admin change
    store = MemoryStore()
    app = _app_with_store(store)
    developer = SimpleNamespace(api_key_fingerprint=FINGERPRINT)
    generation = await get_authentication_generation(store=store, fingerprint=FINGERPRINT)

    # When the admin change evicts the developer, then the stale request writes its entry
    await delete_authentication_cache_for_developer(app, developer)
    await cache_authenticated_developer(
        store=store, fingerprint=FINGERPRINT, value=b"stale", generation=generation
    )

    # Then the stale entry is not left in the cache
    assert await store.get(FINGERPRINT) is None


async def test_cache_authenticated_developer_writes_after_earlier_eviction() -> None:
    """Verify a request that starts after an eviction caches the fresh developer."""
    # Given an eviction that finished before this request read the generation
    store = MemoryStore()
    app = _app_with_store(store)
    await delete_authentication_cache_for_developer(
        app, SimpleNamespace(api_key_fingerprint=FINGERPRINT)
    )
    generation = await get_authentication_generation(store=store, fingerprint=FINGERPRINT)

    # When the developer is cached
    await cache_authenticated_developer(
        store=store, fingerprint=FINGERPRINT, value=b"fresh", generation=generation
    )

    # Then the entry is stored
    assert await store.get(FINGERPRINT) == b"fresh"
