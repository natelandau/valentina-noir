"""Manage session storage."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

from litestar.config.response_cache import default_cache_key_builder

from vapi.config import settings
from vapi.constants import AUTH_HEADER_KEY, ON_BEHALF_OF_HEADER_KEY
from vapi.lib.crypt import hmac_sha256_hex

if TYPE_CHECKING:
    from litestar import Litestar, Request
    from litestar.stores.base import Store

    from vapi.db.sql_models.developer import Developer


logger = logging.getLogger("vapi")

__all__ = (
    "cache_authenticated_developer",
    "claim_store_key",
    "delete_authentication_cache_for_developer",
    "delete_response_cache_for_api_key",
    "delete_response_cache_for_company",
    "get_authentication_generation",
    "response_cache_key_builder",
)


def response_cache_key_builder(request: Request) -> str:
    """Create a cache key for the response cache.

    The cache key combines the API key fingerprint, the acting end-user from the
    On-Behalf-Of header, and the request method and path parameters.

    The acting user is part of the key because responses are role-dependent (for
    example, storyteller characters are hidden from players). A single API key is
    shared across end-users, so omitting On-Behalf-Of would let one user receive
    another user's cached, role-filtered response.

    Args:
        request (Request): Current request instance.


    Returns:
        str: App slug prefixed cache key.
    """
    fingerprint = hmac_sha256_hex(data=request.headers.get(AUTH_HEADER_KEY, ""))
    acting_user = request.headers.get(ON_BEHALF_OF_HEADER_KEY) or ""
    return f"{fingerprint}:{acting_user}:{default_cache_key_builder(request)}"


async def delete_authentication_cache_for_developer(
    app: Litestar, developer: Developer, *, fingerprint: str | None = None
) -> None:
    """Evict a developer's API key from the authentication cache.

    Cached authentication skips the database, so call this after rotating a key, archiving
    a developer, or changing their privileges. The change then applies on the next request
    instead of when the cache entry expires.

    Args:
        app (Litestar): The application that owns the authentication store.
        developer (Developer): The developer whose cached authentication to evict.
        fingerprint (str | None): The key fingerprint to evict. Pass the pre-rotation
            fingerprint after rotating a key; defaults to the developer's current one.
    """
    fingerprint = fingerprint or developer.api_key_fingerprint
    if not fingerprint:
        return

    store = app.stores.get(settings.stores.authentication_cache_key)
    # Bump the generation before deleting so an in-flight cache miss that read the
    # developer row before this change sees the new generation and drops its write.
    await store.set(
        _authentication_generation_key(fingerprint),
        uuid4().hex,
        expires_in=settings.stores.ttl,
    )
    await store.delete(fingerprint)


async def claim_store_key(*, store: Store, key: str, value: bytes, expires_in: int) -> bool:
    """Claim a store key so only one caller acts on it until it expires or is released.

    Use to deduplicate work across concurrent requests. Stores with an atomic
    set-if-absent (the app's Redis store) use it; other stores serve single-process
    apps such as tests, where check-then-set suffices.

    Args:
        store (Store): The store holding the claim.
        key (str): The key to claim.
        value (bytes): The value to store, e.g. a token the claimant can check on release.
        expires_in (int): Seconds before the claim lapses on its own.

    Returns:
        bool: True if this call claimed the key, False if another caller holds it.
    """
    set_if_absent = getattr(store, "set_if_absent", None)
    if set_if_absent is not None:
        return await set_if_absent(key, value, expires_in=expires_in)
    if await store.exists(key):
        return False
    await store.set(key, value, expires_in=expires_in)
    return True


def _authentication_generation_key(fingerprint: str) -> str:
    """Return the store key holding the eviction generation for an API key fingerprint."""
    return f"generation:{fingerprint}"


async def get_authentication_generation(*, store: Store, fingerprint: str) -> bytes | None:
    """Read the eviction generation for an API key fingerprint.

    Read it before loading the developer from the database and pass it to
    ``cache_authenticated_developer``, so an eviction that lands in between is detected.

    Args:
        store (Store): The authentication cache store.
        fingerprint (str): The API key fingerprint.

    Returns:
        bytes | None: The current generation, or None if the key was not evicted recently.
    """
    return await store.get(_authentication_generation_key(fingerprint))


async def cache_authenticated_developer(
    *, store: Store, fingerprint: str, value: bytes, generation: bytes | None
) -> None:
    """Cache a developer's authentication unless it was evicted since the database read.

    A request that read the developer row before an admin change could otherwise
    re-cache the stale row after the change evicted it. The generation is checked
    after the write: an eviction bumps the generation before it deletes, so either
    the eviction's delete removes this write or this check sees the new generation.

    Args:
        store (Store): The authentication cache store.
        fingerprint (str): The API key fingerprint used as the cache key.
        value (bytes): The encoded cached developer.
        generation (bytes | None): The generation read before the database lookup.
    """
    await store.set(fingerprint, value, expires_in=settings.stores.ttl)
    if await get_authentication_generation(store=store, fingerprint=fingerprint) != generation:
        await store.delete(fingerprint)


async def delete_response_cache_for_company(request: Request, company_id: str) -> None:
    """Delete every developer's cached responses for a company's routes and company lists.

    Several developers can share a company, so a write by one must also clear the
    others' cached copies of that company's data. Company lists embed each company's
    data and resource counts, and are indexed only by developer, so every cached
    company list is cleared too. That also drops a revoked developer's list.

    Args:
        request (Request): Current request instance.
        company_id (str): The company whose cached routes to clear.
    """
    store = request.app.stores.get(settings.stores.response_cache_key)
    await store.delete_indexed("company", company_id)  # ty:ignore[unresolved-attribute]
    await store.delete_indexed("company_list", "all")  # ty:ignore[unresolved-attribute]


async def delete_response_cache_for_api_key(request: Request) -> None:
    """Delete the response cache for the API key.

    Args:
        request (Request): Current request instance.
    """
    fingerprint = hmac_sha256_hex(data=request.headers.get(AUTH_HEADER_KEY, ""))

    store = request.app.stores.get(settings.stores.response_cache_key)
    await store.delete_indexed("developer", fingerprint)  # ty:ignore[unresolved-attribute]
