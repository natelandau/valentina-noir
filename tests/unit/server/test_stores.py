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


def _request_for(store: RedisStore) -> Any:
    """Return a stand-in request whose app's store registry always yields the given store."""
    return SimpleNamespace(app=SimpleNamespace(stores=SimpleNamespace(get=lambda _: store)))


async def test_delete_indexed_removes_only_the_company_entries(
    redis: Any, mocker: MockerFixture
) -> None:
    """Verify a company flush deletes that company's cached responses without scanning."""
    # Given cached responses for two companies
    store = _response_cache(redis)
    company, other = str(uuid4()), str(uuid4())
    await store.set(f"fp1:0::GET/api/v1/companies/{company}/users", b"a", expires_in=60)
    await store.set(f"fp2:0::GET/api/v1/companies/{other}/users", b"b", expires_in=60)
    scan = mocker.patch.object(redis, "scan_iter", side_effect=AssertionError("scanned"))

    # When flushing one company
    await store.delete_indexed("company", company)

    # Then only its entry is gone, and no scan ran
    assert await store.get(f"fp1:0::GET/api/v1/companies/{company}/users") is None
    assert await store.get(f"fp2:0::GET/api/v1/companies/{other}/users") == b"b"
    scan.assert_not_called()


async def test_delete_indexed_removes_a_developers_entries(redis: Any) -> None:
    """Verify a developer flush deletes every cached response for that API key fingerprint."""
    # Given cached responses for one developer under two paths
    store = _response_cache(redis)
    await store.set("fp1:0::GET/api/v1/developers/me", b"a", expires_in=60)
    await store.set(f"fp1:0::GET/api/v1/companies/{uuid4()}", b"b", expires_in=60)

    # When flushing the developer
    await store.delete_indexed("developer", "fp1")

    # Then both entries are gone
    assert await store.get("fp1:0::GET/api/v1/developers/me") is None


async def test_delete_indexed_clears_non_canonical_company_spelling(redis: Any) -> None:
    """Verify a company flush with the canonical ID clears entries cached under an uppercase ID."""
    # Given a response cached under an uppercase spelling of the company ID
    store = _response_cache(redis)
    company = str(uuid4())
    key = f"fp1:0::GET/api/v1/companies/{company.upper()}/users"
    await store.set(key, b"a", expires_in=60)

    # When flushing the company by its canonical ID
    await store.delete_indexed("company", company)

    # Then the uppercase entry is gone
    assert await store.get(key) is None


async def test_company_list_is_cleared_by_any_company_flush(redis: Any) -> None:
    """Verify every developer's cached company list is cleared when a company is flushed."""
    # Given two developers' cached company lists and an unrelated cached response
    store = _response_cache(redis)
    request = _request_for(store)
    list_one = "fp1:6:user-a:GET/api/v1/companies?limit=10&offset=0"
    list_two = "fp2:0::GET/api/v1/companies"
    other = "fp2:0::GET/api/v1/developers/me"
    for key in (list_one, list_two, other):
        await store.set(key, b"x", expires_in=60)

    # When any company's responses are flushed
    await delete_response_cache_for_company(request, str(uuid4()))  # ty:ignore[invalid-argument-type]

    # Then both company lists are gone and the unrelated entry remains
    assert await store.get(list_one) is None
    assert await store.get(list_two) is None
    assert await store.get(other) == b"x"


async def test_company_flush_through_dashless_id_clears_dashed_entries(redis: Any) -> None:
    """Verify a write through a dashless company path clears another developer's dashed entry."""
    # Given another developer's response cached under the dashed company ID
    store = _response_cache(redis)
    request = _request_for(store)
    company = uuid4()
    key = f"fp2:0::GET/api/v1/companies/{company}/users"
    await store.set(key, b"a", expires_in=60)

    # When a write through the dashless path flushes the company
    await delete_response_cache_for_company(request, company.hex)  # ty:ignore[invalid-argument-type]

    # Then the dashed entry is gone
    assert await store.get(key) is None


async def test_entry_cached_through_dashless_path_is_company_indexed(redis: Any) -> None:
    """Verify a response cached through a dashless company path is cleared by a company flush."""
    # Given a response cached through the dashless spelling of the company ID
    store = _response_cache(redis)
    company = uuid4()
    key = f"fp1:0::GET/api/v1/companies/{company.hex.upper()}/users"
    await store.set(key, b"a", expires_in=60)

    # When flushing the company by its canonical ID
    await store.delete_indexed("company", str(company))

    # Then the dashless entry is gone
    assert await store.get(key) is None


async def test_company_flush_changes_the_generation_of_its_entries(redis: Any) -> None:
    """Verify a company flush changes the generation of that company's keys, not others'."""
    # Given keys for two companies and their generations
    store = _response_cache(redis)
    company, other = uuid4(), uuid4()
    key = f"fp1:0::GET/api/v1/companies/{company}/users"
    other_key = f"fp1:0::GET/api/v1/companies/{other}/users"
    before, other_before = await store.generations(key), await store.generations(other_key)

    # When flushing one company through its dashless ID
    await store.delete_indexed("company", company.hex)

    # Then only that company's key sees a new generation
    assert await store.generations(key) != before
    assert await store.generations(other_key) == other_before


async def test_acting_user_cannot_pose_as_the_company_path(redis: Any) -> None:
    """Verify a company path inside On-Behalf-Of does not change which company an entry indexes."""
    # Given a response cached for one company by an acting user named like another company's path
    store = _response_cache(redis)
    company, decoy = uuid4(), uuid4()
    acting_user = f"/companies/{decoy}"
    key = f"fp1:{len(acting_user)}:{acting_user}:GET/api/v1/companies/{company}/users"
    await store.set(key, b"a", expires_in=60)

    # When flushing the company in the path
    await store.delete_indexed("company", str(company))

    # Then the entry is gone
    assert await store.get(key) is None


async def test_index_outlives_its_longest_lived_entry(redis: Any) -> None:
    """Verify a shorter-lived entry does not shorten the index of a longer-lived one."""
    # Given a developer's long-lived entry, then a short-lived one
    store = _response_cache(redis)
    await store.set("fp1:0::GET/api/v1/options", b"a", expires_in=600)
    await store.set("fp1:0::GET/api/v1/developers/me", b"b", expires_in=60)

    # When reading the developer index's remaining life
    ttl = await redis.ttl(
        f"{settings.slug}:{settings.stores.response_cache_key}_index:developer:fp1"
    )

    # Then it still covers the long-lived entry
    assert ttl > 60


async def test_company_segment_ending_in_generation_cannot_flush_a_generation_key(
    redis: Any,
) -> None:
    """Verify a company path segment ending in ':generation' is not read as a generation key."""
    # Given a company whose generation was set by a flush
    store = _response_cache(redis)
    company = uuid4()
    key = f"fp1:0::GET/api/v1/companies/{company}/users"
    await store.delete_indexed("company", str(company))
    before = await store.generations(key)

    # When flushing a company "ID" spelled as that company's index plus ":generation"
    await store.delete_indexed("company", f"{company}:generation")

    # Then the real company's generation is untouched
    assert await store.generations(key) == before
