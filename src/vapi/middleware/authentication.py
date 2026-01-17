"""Custom authentication middleware."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from litestar.middleware import DefineMiddleware
from litestar.middleware.authentication import (
    AbstractAuthenticationMiddleware,
    AuthenticationResult,
)
from litestar.serialization import decode_json, encode_json

from vapi.config import settings
from vapi.constants import AUTH_HEADER_KEY
from vapi.db.models import Developer
from vapi.lib.crypt import hmac_sha256_hex
from vapi.lib.exceptions import NotAuthorizedError

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection

logger = logging.getLogger("vapi")

__all__ = ("auth_mw",)


class TokenAuthMiddleware(AbstractAuthenticationMiddleware):
    """Token authentication middleware."""

    async def authenticate_request(self, connection: ASGIConnection) -> AuthenticationResult:
        """Given a request, parse the request api key stored in the header and retrieve the user correlating to the token from the DB."""
        # retrieve the auth header
        auth_header = connection.headers.get(AUTH_HEADER_KEY)
        if not auth_header:
            raise NotAuthorizedError(detail="API key not provided")

        # Fast deterministic lookup by HMAC fingerprint, then Argon2 verify
        fingerprint = hmac_sha256_hex(data=auth_header)

        # Use StoreRegistry Redis store like rate_limit middleware (namespaced as "<slug>:auth")
        store = connection.app.stores.get(settings.stores.authentication_cache_key)
        cache_key = f"{fingerprint}"

        # Try cache first
        cached = await store.get(cache_key, renew_for=settings.stores.ttl)
        if cached is not None:
            data = decode_json(cached)
            developer = Developer(**data)

            return AuthenticationResult(user=developer, auth=auth_header)

        # Cache miss: DB lookup and verify
        developer = await Developer.find_one(
            Developer.api_key_fingerprint == fingerprint,
            Developer.is_archived == False,
        )
        if developer and await developer.verify_api_key(auth_header):
            # Serialize to JSON-safe types to avoid PydanticObjectId errors
            public_json = developer.model_dump(
                exclude={"hashed_api_key", "api_key_fingerprint"}, mode="json"
            )
            await store.set(
                cache_key,
                encode_json(public_json),
                expires_in=settings.stores.ttl,
            )

            return AuthenticationResult(user=developer, auth=auth_header)

        raise NotAuthorizedError(detail="Unauthorized API key")


auth_mw = DefineMiddleware(TokenAuthMiddleware, exclude=["schema", "docs", "^/public/", "^/saq"])
