"""Tests for provider token verification."""

import json
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pytest_mock import MockerFixture

from vapi.config import settings
from vapi.constants import IdentityProvider
from vapi.lib.exceptions import ServiceUnavailableError, UnprocessableEntityError
from vapi.utils.identity import VerifiedIdentity, verify_provider_token

pytestmark = pytest.mark.anyio

KID = "test-kid"
AUDIENCE = "com.example.testapp"


@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[Any, dict[str, Any]]:
    """Generate an RSA keypair and its public JWKS entry."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk["kid"] = KID
    jwk["alg"] = "RS256"
    jwk["use"] = "sig"
    return private_key, {"keys": [jwk]}


def _sign_token(private_key: Any, *, kid: str = KID, **claim_overrides: Any) -> str:
    """Sign an Apple-style ID token with the test key."""
    claims: dict[str, Any] = {
        "iss": "https://appleid.apple.com",
        "aud": AUDIENCE,
        "exp": int(time.time()) + 600,
        "iat": int(time.time()),
        "sub": "apple-sub-001",
        "email": "user@example.com",
        "email_verified": True,
    }
    claims.update(claim_overrides)
    # Drop keys whose override value is None so tests can exercise genuinely absent claims
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


class TestOIDCVerification:
    """Test Apple/Google ID token verification."""

    @pytest.fixture(autouse=True)
    def _configure(self, mocker: MockerFixture, rsa_keypair: tuple[Any, dict[str, Any]]) -> Any:
        """Allow the test audience and serve the test JWKS instead of hitting the network."""
        mocker.patch.object(settings.oauth, "apple_audiences", [AUDIENCE])
        mocker.patch.object(settings.oauth, "google_audiences", [AUDIENCE])
        fetch_mock = mocker.AsyncMock(return_value=rsa_keypair[1])
        mocker.patch("vapi.utils.identity._fetch_jwks", new=fetch_mock)
        return fetch_mock

    async def test_valid_apple_token(self, rsa_keypair: tuple[Any, dict[str, Any]]) -> None:
        """Verify a valid Apple ID token resolves to a VerifiedIdentity."""
        # Given a validly signed Apple ID token
        token = _sign_token(rsa_keypair[0])

        # When the token is verified
        identity = await verify_provider_token(provider=IdentityProvider.APPLE, token=token)

        # Then the identity is normalized with a verified email
        assert identity == VerifiedIdentity(
            provider="apple",
            provider_id="apple-sub-001",
            email="user@example.com",
            email_verified=True,
            profile={"id": "apple-sub-001", "email": "user@example.com"},
        )

    async def test_valid_google_token(self, rsa_keypair: tuple[Any, dict[str, Any]]) -> None:
        """Verify a valid Google ID token resolves, including the bare issuer form."""
        # Given a Google-issued token using the no-scheme issuer
        token = _sign_token(rsa_keypair[0], iss="accounts.google.com", sub="google-sub-9")

        # When the token is verified
        identity = await verify_provider_token(provider=IdentityProvider.GOOGLE, token=token)

        # Then the identity is resolved
        assert identity.provider == "google"
        assert identity.provider_id == "google-sub-9"
        assert identity.email_verified is True

    async def test_email_verified_string_true(
        self, rsa_keypair: tuple[Any, dict[str, Any]]
    ) -> None:
        """Verify Apple's string-typed email_verified claim is handled."""
        # Given a token where email_verified is the string "true"
        token = _sign_token(rsa_keypair[0], email_verified="true")

        # When the token is verified
        identity = await verify_provider_token(provider=IdentityProvider.APPLE, token=token)

        # Then the email counts as verified
        assert identity.email_verified is True

    async def test_unverified_email(self, rsa_keypair: tuple[Any, dict[str, Any]]) -> None:
        """Verify an unverified email claim yields email_verified False."""
        # Given a token with an unverified email
        token = _sign_token(rsa_keypair[0], email_verified=False)

        # When the token is verified
        identity = await verify_provider_token(provider=IdentityProvider.APPLE, token=token)

        # Then the email is present but not verified
        assert identity.email == "user@example.com"
        assert identity.email_verified is False

    async def test_expired_token(self, rsa_keypair: tuple[Any, dict[str, Any]]) -> None:
        """Verify an expired token is rejected with 422."""
        # Given an expired token
        token = _sign_token(rsa_keypair[0], exp=int(time.time()) - 60)

        # When the token is verified
        # Then verification fails
        with pytest.raises(UnprocessableEntityError):
            await verify_provider_token(provider=IdentityProvider.APPLE, token=token)

    async def test_wrong_audience(self, rsa_keypair: tuple[Any, dict[str, Any]]) -> None:
        """Verify a token for an unknown client app is rejected."""
        # Given a token minted for a different audience
        token = _sign_token(rsa_keypair[0], aud="com.evil.other")

        # When the token is verified
        # Then verification fails
        with pytest.raises(UnprocessableEntityError):
            await verify_provider_token(provider=IdentityProvider.APPLE, token=token)

    async def test_wrong_issuer(self, rsa_keypair: tuple[Any, dict[str, Any]]) -> None:
        """Verify a token with an unexpected issuer is rejected."""
        # Given a token with the wrong issuer
        token = _sign_token(rsa_keypair[0], iss="https://evil.example.com")

        # When the token is verified
        # Then verification fails
        with pytest.raises(UnprocessableEntityError):
            await verify_provider_token(provider=IdentityProvider.APPLE, token=token)

    async def test_unknown_kid(
        self,
        rsa_keypair: tuple[Any, dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """Verify a token signed with an unknown key is rejected after one cache-bypass refetch."""
        # Given a fresh fetch mock so we can inspect its call count
        fetch_mock = mocker.AsyncMock(return_value=rsa_keypair[1])
        mocker.patch("vapi.utils.identity._fetch_jwks", new=fetch_mock)

        # Given a token signed with a kid absent from the JWKS
        token = _sign_token(rsa_keypair[0], kid="rotated-away")

        # When the token is verified
        # Then verification fails
        with pytest.raises(UnprocessableEntityError):
            await verify_provider_token(provider=IdentityProvider.APPLE, token=token)

        # And the JWKS was fetched twice (initial + one cache-bypass refetch)
        assert fetch_mock.call_count == 2

    async def test_empty_audience_allowlist_fails_closed(
        self, mocker: MockerFixture, rsa_keypair: tuple[Any, dict[str, Any]]
    ) -> None:
        """Verify a provider with no configured audiences is disabled."""
        # Given an empty audience allowlist
        mocker.patch.object(settings.oauth, "apple_audiences", [])
        token = _sign_token(rsa_keypair[0])

        # When the token is verified
        # Then verification fails closed
        with pytest.raises(UnprocessableEntityError):
            await verify_provider_token(provider=IdentityProvider.APPLE, token=token)

    async def test_garbage_token(self) -> None:
        """Verify a non-JWT string is rejected."""
        # Given a garbage token string
        token = "not-a-jwt"  # noqa: S105

        # When the token is verified
        # Then verification fails
        with pytest.raises(UnprocessableEntityError):
            await verify_provider_token(provider=IdentityProvider.APPLE, token=token)

    async def test_jwks_endpoint_unreachable(
        self, mocker: MockerFixture, rsa_keypair: tuple[Any, dict[str, Any]]
    ) -> None:
        """Verify a provider outage surfaces as 503, not 422."""
        # Given a JWKS endpoint that is down
        mocker.patch(
            "vapi.utils.identity._fetch_jwks",
            new=mocker.AsyncMock(side_effect=ServiceUnavailableError(detail="down")),
        )
        token = _sign_token(rsa_keypair[0])

        # When the token is verified
        # Then the outage propagates
        with pytest.raises(ServiceUnavailableError):
            await verify_provider_token(provider=IdentityProvider.APPLE, token=token)

    async def test_missing_email_claim(self, rsa_keypair: tuple[Any, dict[str, Any]]) -> None:
        """Verify a valid token without an email claim yields no verified email."""
        # Given a token with no email claims
        token = _sign_token(rsa_keypair[0], email=None, email_verified=None)

        # When the token is verified
        identity = await verify_provider_token(provider=IdentityProvider.APPLE, token=token)

        # Then no email is present and it is not verified
        assert identity.email is None
        assert identity.email_verified is False
