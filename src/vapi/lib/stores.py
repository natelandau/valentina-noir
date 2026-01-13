"""Manage session storage."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from litestar.config.response_cache import default_cache_key_builder

from vapi.config import settings
from vapi.constants import AUTH_HEADER_KEY
from vapi.lib.crypt import hmac_sha256_hex

if TYPE_CHECKING:
    from litestar import Request


logger = logging.getLogger("vapi")

__all__ = (
    "delete_authentication_cache_for_api_key",
    "delete_response_cache_for_api_key",
    "response_cache_key_builder",
)


def response_cache_key_builder(request: Request) -> str:
    """Create a cache key for the response cache.

    The cache key is a combination of the API key fingerprint followed by the request method and path parameters.

    Args:
        request (Request): Current request instance.


    Returns:
        str: App slug prefixed cache key.
    """
    fingerprint = hmac_sha256_hex(data=request.headers.get(AUTH_HEADER_KEY))
    return f"{fingerprint}:{default_cache_key_builder(request)}"


async def delete_authentication_cache_for_api_key(request: Request) -> None:
    """Delete the authentication cache for the API key.

    Args:
        request (Request): Current request instance.
    """
    fingerprint = hmac_sha256_hex(data=request.headers.get(AUTH_HEADER_KEY))
    store = request.app.stores.get(f"{settings.stores.authentication_cache_key}:{fingerprint}")

    # The delete_by_prefix method calls redis directly, so we need to include the namespace even though it is already included in the store
    await store.delete_by_prefix(match=f"{settings.stores.authentication_cache_key}:{fingerprint}")  # type: ignore [attr-defined]


async def delete_response_cache_for_api_key(request: Request) -> None:
    """Delete the response cache for the API key.

    Args:
        request (Request): Current request instance.
    """
    fingerprint = hmac_sha256_hex(data=request.headers.get(AUTH_HEADER_KEY))

    store = request.app.stores.get(f"{settings.stores.response_cache_key}:{fingerprint}")

    # The delete_by_prefix method calls redis directly, so we need to include the namespace even though it is already included in the store
    await store.delete_by_prefix(match=f"{settings.stores.response_cache_key}:{fingerprint}")  # type: ignore [attr-defined]
