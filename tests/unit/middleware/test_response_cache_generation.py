"""Tests for dropping response-cache writes that a concurrent flush made stale."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import httpx
import pytest
from litestar import Litestar, Request, get
from litestar.config.response_cache import ResponseCacheConfig
from litestar.stores.registry import StoreRegistry

from vapi.config import settings
from vapi.lib.stores import delete_response_cache_for_company, response_cache_key_builder
from vapi.middleware.response_cache_generation import response_cache_generation_middleware
from vapi.server.stores import RedisStore

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


def _build_app(redis: Any, *, flush_during_read: Callable[[], bool]) -> tuple[Litestar, list[int]]:
    """Build an app with one cached company route that counts how often its handler runs."""
    calls: list[int] = []

    @get("/api/v1/companies/{company_id:str}/thing", cache=True)
    async def _thing(request: Request, company_id: str) -> dict:
        calls.append(1)
        if flush_during_read():
            # A write commits and flushes the company after this request read the database
            await delete_response_cache_for_company(request, company_id)
        return {"call": len(calls)}

    app = Litestar(
        route_handlers=[_thing],
        middleware=[response_cache_generation_middleware],
        response_cache_config=ResponseCacheConfig(
            key_builder=response_cache_key_builder, store=settings.stores.response_cache_key
        ),
        stores=StoreRegistry(
            default_factory=lambda name: RedisStore(redis, namespace=f"{settings.slug}:{name}")
        ),
    )
    return app, calls


def _client(app: Litestar) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_response_read_before_a_company_flush_is_not_cached(redis: Any) -> None:
    """Verify a GET that read the database before a company flush does not cache its response."""
    # Given a cached route whose first read is overtaken by a company write's flush
    flushes = iter([True])
    app, calls = _build_app(redis, flush_during_read=lambda: next(flushes, False))
    path = f"/api/v1/companies/{uuid4()}/thing"

    # When the route is read twice
    async with _client(app) as client:
        await client.get(path)
        second = await client.get(path)

    # Then the stale first response was not served from the cache
    assert len(calls) == 2
    assert second.json() == {"call": 2}


async def test_response_without_a_concurrent_flush_is_cached(redis: Any) -> None:
    """Verify a GET with no concurrent flush is cached and served from the cache."""
    # Given a cached route with no concurrent writes
    app, calls = _build_app(redis, flush_during_read=lambda: False)
    path = f"/api/v1/companies/{uuid4()}/thing"

    # When the route is read twice
    async with _client(app) as client:
        await client.get(path)
        second = await client.get(path)

    # Then the second read came from the cache
    assert len(calls) == 1
    assert second.json() == {"call": 1}
