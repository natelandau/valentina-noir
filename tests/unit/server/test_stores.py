"""Unit tests for the app's Redis store."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from vapi.config import settings
from vapi.lib.stores import delete_response_cache_for_company
from vapi.server.stores import RedisStore

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


def _response_cache(redis: Any) -> RedisStore:
    return RedisStore(redis, namespace=f"{settings.slug}:{settings.stores.response_cache_key}")


async def test_delete_indexed_removes_only_the_company_entries(
    redis: Any, mocker: MockerFixture
) -> None:
    """Verify a company flush deletes that company's cached responses without scanning."""
    # Given cached responses for two companies
    store = _response_cache(redis)
    company, other = str(uuid4()), str(uuid4())
    await store.set(f"fp1::/api/v1/companies/{company}/users", b"a", expires_in=60)
    await store.set(f"fp2::/api/v1/companies/{other}/users", b"b", expires_in=60)
    scan = mocker.patch.object(redis, "scan_iter", side_effect=AssertionError("scanned"))

    # When flushing one company
    await store.delete_indexed("company", company)

    # Then only its entry is gone, and no scan ran
    assert await store.get(f"fp1::/api/v1/companies/{company}/users") is None
    assert await store.get(f"fp2::/api/v1/companies/{other}/users") == b"b"
    scan.assert_not_called()


async def test_delete_indexed_removes_a_developers_entries(redis: Any) -> None:
    """Verify a developer flush deletes every cached response for that API key fingerprint."""
    # Given cached responses for one developer under two paths
    store = _response_cache(redis)
    await store.set("fp1::/api/v1/developers/me", b"a", expires_in=60)
    await store.set(f"fp1::/api/v1/companies/{uuid4()}", b"b", expires_in=60)

    # When flushing the developer
    await store.delete_indexed("developer", "fp1")

    # Then both entries are gone
    assert await store.get("fp1::/api/v1/developers/me") is None


async def test_delete_indexed_clears_non_canonical_company_spelling(redis: Any) -> None:
    """Verify a company flush with the canonical ID clears entries cached under an uppercase ID."""
    # Given a response cached under an uppercase spelling of the company ID
    store = _response_cache(redis)
    company = str(uuid4())
    key = f"fp1::GET/api/v1/companies/{company.upper()}/users"
    await store.set(key, b"a", expires_in=60)

    # When flushing the company by its canonical ID
    await store.delete_indexed("company", company)

    # Then the uppercase entry is gone
    assert await store.get(key) is None


async def test_company_list_is_cleared_by_any_company_flush(redis: Any) -> None:
    """Verify every developer's cached company list is cleared when a company is flushed."""
    # Given two developers' cached company lists and an unrelated cached response
    store = _response_cache(redis)
    request = SimpleNamespace(app=SimpleNamespace(stores=SimpleNamespace(get=lambda _: store)))
    list_one = "fp1:user-a:GET/api/v1/companieslimit=10&offset=0"
    list_two = "fp2::GET/api/v1/companies"
    other = "fp2::GET/api/v1/developers/me"
    for key in (list_one, list_two, other):
        await store.set(key, b"x", expires_in=60)

    # When any company's responses are flushed
    await delete_response_cache_for_company(request, str(uuid4()))  # ty:ignore[invalid-argument-type]

    # Then both company lists are gone and the unrelated entry remains
    assert await store.get(list_one) is None
    assert await store.get(list_two) is None
    assert await store.get(other) == b"x"
