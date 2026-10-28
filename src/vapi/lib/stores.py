"""Manage session storage."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from litestar.config.response_cache import default_cache_key_builder

from vapi.config import settings
from vapi.constants import AUTH_HEADER_KEY, ON_BEHALF_OF_HEADER_KEY
from vapi.lib.crypt import hmac_sha256_hex

if TYPE_CHECKING:
    from litestar import Litestar, Request

    from vapi.db.sql_models.developer import Developer


logger = logging.getLogger("vapi")

__all__ = (
    "delete_authentication_cache_for_developer",
    "delete_response_cache_for_api_key",
    "delete_response_cache_for_company",
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
    await store.delete(fingerprint)


async def delete_response_cache_for_company(request: Request, company_id: str) -> None:
    """Delete every developer's cached responses for a company's routes.

    Several developers can share a company, so a write by one must also clear the
    others' cached copies of that company's data.

    Args:
        request (Request): Current request instance.
        company_id (str): The company whose cached routes to clear.
    """
    store = request.app.stores.get(settings.stores.response_cache_key)
    await store.delete_indexed("company", company_id)  # ty:ignore[unresolved-attribute]


async def delete_response_cache_for_api_key(request: Request) -> None:
    """Delete the response cache for the API key.

    Args:
        request (Request): Current request instance.
    """
    fingerprint = hmac_sha256_hex(data=request.headers.get(AUTH_HEADER_KEY, ""))

    store = request.app.stores.get(settings.stores.response_cache_key)
    await store.delete_indexed("developer", fingerprint)  # ty:ignore[unresolved-attribute]
