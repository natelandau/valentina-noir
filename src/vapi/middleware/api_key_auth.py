"""Custom authentication middleware."""

import logging
from typing import TYPE_CHECKING
from uuid import UUID

import msgspec
from litestar.middleware import DefineMiddleware
from litestar.middleware.authentication import (
    AbstractAuthenticationMiddleware,
    AuthenticationResult,
)

from vapi.config import settings
from vapi.constants import AUTH_HEADER_KEY
from vapi.db.sql_models.developer import Developer
from vapi.domain.services.developer_svc import DeveloperService
from vapi.lib.crypt import hmac_sha256_hex
from vapi.lib.exceptions import NotAuthorizedError

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection

logger = logging.getLogger("vapi")

__all__ = ("CachedDeveloper", "api_key_auth_mw")


class CachedDeveloper(msgspec.Struct):
    """Lightweight developer representation cached in Redis and set as connection.user.

    Only includes fields that guards and dependency providers read from request.user.
    """

    id: UUID
    is_global_admin: bool


class TokenAuthMiddleware(AbstractAuthenticationMiddleware):
    """Token authentication middleware."""

    async def authenticate_request(self, connection: "ASGIConnection") -> AuthenticationResult:
        """Authenticate a request by API key stored in the header."""
        auth_header = connection.headers.get(AUTH_HEADER_KEY)
        if not auth_header:
            raise NotAuthorizedError(detail="API key not provided")

        fingerprint = hmac_sha256_hex(data=auth_header)
        store = connection.app.stores.get(settings.stores.authentication_cache_key)
        cache_key = fingerprint

        # Try cache first
        cached = await store.get(cache_key, renew_for=settings.stores.ttl)
        if cached is not None:
            developer = msgspec.json.decode(cached, type=CachedDeveloper)
            return AuthenticationResult(user=developer, auth=auth_header)

        # Cache miss: DB lookup and verify
        db_developer = await Developer.filter(
            api_key_fingerprint=fingerprint,
            is_archived=False,
        ).first()

        if db_developer:
            svc = DeveloperService()
            if await svc.verify_api_key(db_developer, auth_header):
                cached_dev = CachedDeveloper(
                    id=db_developer.id,
                    is_global_admin=db_developer.is_global_admin,
                )
                await store.set(
                    cache_key,
                    msgspec.json.encode(cached_dev),
                    expires_in=settings.stores.ttl,
                )
                return AuthenticationResult(user=cached_dev, auth=auth_header)

        raise NotAuthorizedError(detail="Unauthorized API key")


api_key_auth_mw = DefineMiddleware(
    TokenAuthMiddleware, exclude=["schema", "docs", "^/public/", "^/saq"]
)
