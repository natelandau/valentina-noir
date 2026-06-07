"""Provider token verification for identity resolution.

Verifies third-party provider credentials (Apple/Google OIDC ID tokens,
Discord/GitHub OAuth access tokens) and normalizes the result into a
VerifiedIdentity consumed by the identity resolution service.
"""

import json
from typing import TYPE_CHECKING, Any, assert_never, cast

import httpx
import jwt
import msgspec

from vapi.config import settings
from vapi.constants import IdentityProvider
from vapi.lib.exceptions import ServiceUnavailableError, UnprocessableEntityError

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
    from litestar.stores.base import Store

__all__ = ("VerifiedIdentity", "verify_provider_token")

APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUERS = ("https://appleid.apple.com",)
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")


class VerifiedIdentity(msgspec.Struct):
    """Normalized result of verifying a provider credential."""

    provider: str
    provider_id: str
    email: str | None
    email_verified: bool
    profile: dict[str, Any]


async def verify_provider_token(
    *,
    provider: IdentityProvider,
    token: str,
    store: "Store | None" = None,
) -> VerifiedIdentity:
    """Verify a provider credential and return the normalized identity.

    Args:
        provider: Which identity provider issued the credential.
        token: An OIDC ID token (apple/google) or OAuth access token (discord/github).
        store: Optional Redis store for JWKS caching. None skips caching.
    """
    match provider:
        case IdentityProvider.APPLE:
            return await _verify_oidc_token(
                provider=provider,
                token=token,
                jwks_url=APPLE_JWKS_URL,
                issuers=APPLE_ISSUERS,
                audiences=settings.oauth.apple_audiences,
                store=store,
            )
        case IdentityProvider.GOOGLE:
            return await _verify_oidc_token(
                provider=provider,
                token=token,
                jwks_url=GOOGLE_JWKS_URL,
                issuers=GOOGLE_ISSUERS,
                audiences=settings.oauth.google_audiences,
                store=store,
            )
        case IdentityProvider.DISCORD:
            return await _verify_discord_token(token)
        case IdentityProvider.GITHUB:
            return await _verify_github_token(token)
        case _ as unreachable:
            assert_never(unreachable)


async def _fetch_jwks(url: str) -> dict[str, Any]:
    """Fetch a JWKS document from the provider.

    Args:
        url: The JWKS endpoint URL to fetch.
    """
    try:
        async with httpx.AsyncClient(timeout=settings.oauth.identity_http_timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as e:
        raise ServiceUnavailableError(
            detail="Identity provider is unreachable",
            code="PROVIDER_UNAVAILABLE",
        ) from e


async def _get_jwks(
    *,
    url: str,
    provider: str,
    store: "Store | None",
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Return the provider JWKS, using the Redis cache unless force_refresh.

    Args:
        url: The JWKS endpoint URL.
        provider: The provider name, used as part of the cache key.
        store: Optional Redis store for caching. None skips caching.
        force_refresh: Bypass the cache and fetch fresh data.
    """
    cache_key = f"{settings.stores.jwks_key}:{provider}"
    if store is not None and not force_refresh:
        cached = await store.get(cache_key)
        if cached is not None:
            result: dict[str, Any] = msgspec.json.decode(cached)
            return result

    jwks = await _fetch_jwks(url)
    if store is not None:
        await store.set(
            cache_key,
            msgspec.json.encode(jwks),
            expires_in=settings.oauth.jwks_cache_ttl,
        )
    return jwks


def _find_key(jwks: dict[str, Any], kid: str | None) -> dict[str, Any] | None:
    """Find the JWK matching the token's kid.

    Args:
        jwks: The JWKS document containing a "keys" array.
        kid: The key ID from the token header.
    """
    return next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)


async def _verify_oidc_token(
    *,
    provider: IdentityProvider,
    token: str,
    jwks_url: str,
    issuers: tuple[str, ...],
    audiences: list[str],
    store: "Store | None",
) -> VerifiedIdentity:
    """Verify an OIDC ID token signature and claims against the provider JWKS.

    Args:
        provider: The identity provider enum value.
        token: The raw OIDC ID token string.
        jwks_url: The provider's JWKS endpoint.
        issuers: Acceptable issuer claim values for this provider.
        audiences: Configured audience values this server accepts.
        store: Optional Redis store for JWKS caching.
    """
    # Fail closed: a provider with no configured audiences is disabled
    if not audiences:
        raise UnprocessableEntityError(
            detail=f"{provider.value} sign-in is not enabled on this server",
            code="TOKEN_VERIFICATION_FAILED",
        )

    try:
        kid: str | None = jwt.get_unverified_header(token).get("kid")
    except jwt.InvalidTokenError as e:
        raise UnprocessableEntityError(
            detail="Provider token is not a valid JWT",
            code="TOKEN_VERIFICATION_FAILED",
        ) from e

    jwks = await _get_jwks(url=jwks_url, provider=provider.value, store=store)
    key_data = _find_key(jwks, kid)
    if key_data is None:
        # Key rotation: refetch the JWKS once, bypassing the cache
        jwks = await _get_jwks(
            url=jwks_url, provider=provider.value, store=store, force_refresh=True
        )
        key_data = _find_key(jwks, kid)
    if key_data is None:
        raise UnprocessableEntityError(
            detail="Provider token signing key not found",
            code="TOKEN_VERIFICATION_FAILED",
        )

    try:
        public_key = cast(
            "RSAPublicKey", jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))
        )
    except jwt.InvalidKeyError as e:
        raise UnprocessableEntityError(
            detail="Provider token signing key is not usable",
            code="TOKEN_VERIFICATION_FAILED",
        ) from e
    try:
        # Issuer is validated manually below because Google publishes two valid forms
        claims: dict[str, Any] = jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            audience=audiences,
            options={"verify_iss": False, "require": ["sub"]},
        )
    except jwt.InvalidTokenError as e:
        raise UnprocessableEntityError(
            detail="Provider token failed verification",
            code="TOKEN_VERIFICATION_FAILED",
        ) from e

    if claims.get("iss") not in issuers:
        raise UnprocessableEntityError(
            detail="Provider token has an unexpected issuer",
            code="TOKEN_VERIFICATION_FAILED",
        )

    email: str | None = claims.get("email")
    # Apple sends email_verified as the string "true" on some token versions
    email_verified = str(claims.get("email_verified", "")).lower() == "true"
    return VerifiedIdentity(
        provider=provider.value,
        provider_id=claims["sub"],
        email=email,
        email_verified=bool(email and email_verified),
        profile={"id": claims["sub"], "email": email},
    )


async def _verify_discord_token(token: str) -> VerifiedIdentity:
    """Verify a Discord OAuth access token (implemented in a later task).

    Args:
        token: The Discord OAuth access token.
    """
    raise NotImplementedError


async def _verify_github_token(token: str) -> VerifiedIdentity:
    """Verify a GitHub OAuth access token (implemented in a later task).

    Args:
        token: The GitHub OAuth access token.
    """
    raise NotImplementedError
