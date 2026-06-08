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
from httpx_oauth.exceptions import GetProfileError

from vapi.config import settings
from vapi.config.oauth import get_discord_oauth_client
from vapi.constants import IdentityProvider
from vapi.lib.exceptions import ServiceUnavailableError, UnprocessableEntityError

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
    from litestar.stores.base import Store

__all__ = ("VerifiedIdentity", "build_discord_profile", "verify_provider_token")

APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUERS = ("https://appleid.apple.com",)
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"
GITHUB_OK_STATUS = 200
GITHUB_UNAUTHORIZED_STATUS = 401
GITHUB_SERVER_ERROR_STATUS = 500


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
    additional_audiences: list[str] | None = None,
) -> VerifiedIdentity:
    """Verify a provider credential and return the normalized identity.

    For Apple and Google, the accepted audiences are the union of the global
    env-configured list and any additional audiences passed by the caller (e.g.
    audiences registered by the calling developer via PATCH /developers/me).

    Args:
        provider: Which identity provider issued the credential.
        token: An OIDC ID token (apple/google) or OAuth access token (discord/github).
        store: Optional Redis store for JWKS caching. None skips caching.
        additional_audiences: Extra audience values to accept beyond the global
            env list. Only used for Apple and Google (OIDC providers).
    """
    extra: list[str] = additional_audiences or []
    match provider:
        case IdentityProvider.APPLE:
            return await _verify_oidc_token(
                provider=provider,
                token=token,
                jwks_url=APPLE_JWKS_URL,
                issuers=APPLE_ISSUERS,
                audiences=[*settings.oauth.apple_audiences, *extra],
                store=store,
            )
        case IdentityProvider.GOOGLE:
            return await _verify_oidc_token(
                provider=provider,
                token=token,
                jwks_url=GOOGLE_JWKS_URL,
                issuers=GOOGLE_ISSUERS,
                audiences=[*settings.oauth.google_audiences, *extra],
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
    # Use only the provider name as the cache key; the StoreRegistry factory already
    # namespaces the store with the configured prefix (e.g. "vapi:jwks:"), so
    # prepending jwks_key here would produce a double-prefixed key.
    cache_key = provider
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
    # A kid-less token would match the first kid-less JWK entry by accident, so
    # return None immediately to treat the token as unverifiable.
    if kid is None:
        return None
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
    if key_data is None and store is not None:
        # Key rotation: only refetch when a cache exists to bypass; without a
        # store the first fetch is always fresh, so a second call would be pointless.
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
    # Apple sends email_verified as "true" (string) or 1 (integer) on some token versions
    email_verified = str(claims.get("email_verified", "")).lower() in {"true", "1"}
    return VerifiedIdentity(
        provider=provider.value,
        provider_id=claims["sub"],
        email=email,
        email_verified=bool(email and email_verified),
        profile={"id": claims["sub"], "email": email},
    )


def build_discord_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Build the normalized discord_profile dict from a raw Discord API response.

    Produces the canonical 7-key shape that both the identity resolution flow
    and the OAuth callback flow persist to ``User.discord_profile``. Centralizing
    this keeps the two code paths in sync when Discord changes its schema.

    Args:
        profile: The raw profile dict returned by the Discord API or OAuth client.

    Returns:
        Normalized dict with keys: id, username, global_name, avatar_id,
        discriminator, email, verified.
    """
    return {
        "id": str(profile["id"]),
        "username": profile.get("username"),
        "global_name": profile.get("global_name"),
        "avatar_id": profile.get("avatar"),
        "discriminator": profile.get("discriminator"),
        "email": profile.get("email"),
        "verified": profile.get("verified", False),
    }


async def _verify_discord_token(token: str) -> VerifiedIdentity:
    """Verify a Discord OAuth access token by fetching the profile it grants.

    Args:
        token: The Discord OAuth access token.
    """
    try:
        profile = await get_discord_oauth_client().get_profile(token)
    except GetProfileError as e:
        raise UnprocessableEntityError(
            detail="Discord rejected the access token",
            code="TOKEN_VERIFICATION_FAILED",
        ) from e
    except httpx.HTTPError as e:
        raise ServiceUnavailableError(
            detail="Discord is unreachable",
            code="PROVIDER_UNAVAILABLE",
        ) from e

    try:
        provider_id = str(profile["id"])
    except (KeyError, TypeError) as e:
        raise UnprocessableEntityError(
            detail="Discord profile is missing required 'id' field",
            code="TOKEN_VERIFICATION_FAILED",
        ) from e

    email: str | None = profile.get("email")
    discord_profile = build_discord_profile(profile)
    return VerifiedIdentity(
        provider=IdentityProvider.DISCORD.value,
        provider_id=provider_id,
        email=email,
        email_verified=bool(email and profile.get("verified")),
        profile=discord_profile,
    )


def _extract_github_email(
    emails_response: httpx.Response, profile_email: str | None
) -> tuple[str | None, bool]:
    """Extract the best verified email from the GitHub emails API response.

    Raises ServiceUnavailableError on 5xx (provider outage). Falls back to the
    public profile email when the emails endpoint is inaccessible (e.g. 403 no
    user:email scope).

    Args:
        emails_response: The raw httpx response from the GitHub emails endpoint.
        profile_email: The public profile email from the user endpoint, used as fallback.

    Returns:
        Tuple of (email, email_verified).
    """
    # A 5xx is a GitHub outage; raise rather than silently skipping verified-email
    # matching, which would cause auto-link to miss the user.
    # A 4xx (e.g. 403 no user:email scope) is a caller limitation — fall through to
    # the public profile email fallback instead.
    if emails_response.status_code >= GITHUB_SERVER_ERROR_STATUS:
        raise ServiceUnavailableError(
            detail="GitHub is unreachable",
            code="PROVIDER_UNAVAILABLE",
        )
    if emails_response.status_code == GITHUB_OK_STATUS:
        try:
            email_list: list[dict[str, Any]] = emails_response.json()
        except ValueError:
            email_list = []
        # Prefer the verified primary address; tokens without the user:email
        # scope get a 403 here, in which case fall back to the public profile email
        for entry in email_list:
            if entry.get("primary") and entry.get("verified") and "email" in entry:
                return entry["email"], True
    return profile_email, False


async def _verify_github_token(token: str) -> VerifiedIdentity:
    """Verify a GitHub OAuth access token via the user and emails endpoints.

    Args:
        token: The GitHub OAuth access token.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.oauth.identity_http_timeout) as client:
            user_response = await client.get(GITHUB_USER_URL, headers=headers)
            user_response.raise_for_status()
            emails_response = await client.get(GITHUB_EMAILS_URL, headers=headers)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == GITHUB_UNAUTHORIZED_STATUS:
            raise UnprocessableEntityError(
                detail="GitHub rejected the access token",
                code="TOKEN_VERIFICATION_FAILED",
            ) from e
        # 403 can mean rate-limited (not a bad token), and 5xx are server errors;
        # treat all non-401 HTTP errors as a transient provider outage.
        raise ServiceUnavailableError(
            detail="GitHub is unreachable",
            code="PROVIDER_UNAVAILABLE",
        ) from e
    except httpx.HTTPError as e:
        raise ServiceUnavailableError(
            detail="GitHub is unreachable",
            code="PROVIDER_UNAVAILABLE",
        ) from e

    try:
        gh_user = user_response.json()
        provider_id = str(gh_user["id"])
    except (ValueError, KeyError, TypeError) as e:
        raise UnprocessableEntityError(
            detail="GitHub user response is malformed or missing 'id'",
            code="TOKEN_VERIFICATION_FAILED",
        ) from e

    email, email_verified = _extract_github_email(
        emails_response=emails_response,
        profile_email=gh_user.get("email"),
    )

    return VerifiedIdentity(
        provider=IdentityProvider.GITHUB.value,
        provider_id=provider_id,
        email=email,
        email_verified=email_verified,
        profile={"id": provider_id, "login": gh_user.get("login"), "email": email},
    )
