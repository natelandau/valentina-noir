"""Tests for provider token verification."""

import json
import time
from typing import Any

import httpx
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

    async def test_email_verified_integer_one(
        self, rsa_keypair: tuple[Any, dict[str, Any]]
    ) -> None:
        """Verify the integer 1 for email_verified is accepted as verified."""
        # Given a token where email_verified is the integer 1
        token = _sign_token(rsa_keypair[0], email_verified=1)

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
        """Verify a token signed with an unknown key is rejected without a redundant refetch when there is no cache."""
        # Given a fresh fetch mock so we can inspect its call count
        fetch_mock = mocker.AsyncMock(return_value=rsa_keypair[1])
        mocker.patch("vapi.utils.identity._fetch_jwks", new=fetch_mock)

        # Given a token signed with a kid absent from the JWKS
        token = _sign_token(rsa_keypair[0], kid="rotated-away")

        # When the token is verified (no store=None means no cache, so no refetch)
        # Then verification fails
        with pytest.raises(UnprocessableEntityError):
            await verify_provider_token(provider=IdentityProvider.APPLE, token=token)

        # And the JWKS was fetched exactly once (no pointless cache-bypass refetch without a store)
        assert fetch_mock.call_count == 1

    async def test_unknown_kid_refetches_when_cached(
        self,
        rsa_keypair: tuple[Any, dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """Verify a cache miss on a rotated key triggers exactly one network refetch."""
        import msgspec
        from litestar.stores.memory import MemoryStore

        from vapi.utils.identity import VerifiedIdentity, _get_jwks  # noqa: F401

        private_key, good_jwks = rsa_keypair

        # Given a store pre-populated with STALE JWKS that lacks the token's kid
        store = MemoryStore()
        stale_jwks = {"keys": []}  # no matching key
        await store.set("apple", msgspec.json.encode(stale_jwks))

        # Given _fetch_jwks returns the fresh JWKS that contains the key
        fetch_mock = mocker.AsyncMock(return_value=good_jwks)
        mocker.patch("vapi.utils.identity._fetch_jwks", new=fetch_mock)

        # Given a valid token signed with the test kid
        token = _sign_token(private_key)

        # When the token is verified with the cache store
        identity = await verify_provider_token(
            provider=IdentityProvider.APPLE, token=token, store=store
        )

        # Then verification succeeds (the refetch found the key)
        assert isinstance(identity, VerifiedIdentity)
        assert identity.provider_id == "apple-sub-001"

        # And exactly one network fetch happened (the cache was checked first, then one refetch)
        assert fetch_mock.call_count == 1

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


class TestMergedAudienceVerification:
    """Test that additional_audiences merges correctly with the env-configured list."""

    @pytest.fixture(autouse=True)
    def _configure_fetch(
        self, mocker: MockerFixture, rsa_keypair: tuple[Any, dict[str, Any]]
    ) -> None:
        """Serve the test JWKS without hitting the network."""
        mocker.patch(
            "vapi.utils.identity._fetch_jwks", new=mocker.AsyncMock(return_value=rsa_keypair[1])
        )

    async def test_aud_in_env_list_passes(
        self, mocker: MockerFixture, rsa_keypair: tuple[Any, dict[str, Any]]
    ) -> None:
        """Verify a token whose aud appears only in the env list is accepted."""
        # Given the env list contains the audience and additional_audiences is empty
        mocker.patch.object(settings.oauth, "apple_audiences", [AUDIENCE])
        token = _sign_token(rsa_keypair[0], aud=AUDIENCE)

        # When the token is verified with no additional audiences
        identity = await verify_provider_token(
            provider=IdentityProvider.APPLE,
            token=token,
            additional_audiences=[],
        )

        # Then it resolves successfully
        assert identity.provider_id == "apple-sub-001"

    async def test_aud_in_additional_only_passes(
        self, mocker: MockerFixture, rsa_keypair: tuple[Any, dict[str, Any]]
    ) -> None:
        """Verify a token whose aud appears only in additional_audiences is accepted."""
        # Given the env list is empty but additional_audiences contains the audience
        mocker.patch.object(settings.oauth, "apple_audiences", [])
        developer_aud = "com.myapp.client"
        token = _sign_token(rsa_keypair[0], aud=developer_aud)

        # When the token is verified with the developer's registered audience
        identity = await verify_provider_token(
            provider=IdentityProvider.APPLE,
            token=token,
            additional_audiences=[developer_aud],
        )

        # Then it resolves successfully via the developer-registered audience
        assert identity.provider_id == "apple-sub-001"

    async def test_aud_in_neither_list_fails(
        self, mocker: MockerFixture, rsa_keypair: tuple[Any, dict[str, Any]]
    ) -> None:
        """Verify a token whose aud is in neither source is rejected."""
        # Given neither source contains the token's audience
        mocker.patch.object(settings.oauth, "apple_audiences", ["com.other.app"])
        token = _sign_token(rsa_keypair[0], aud="com.evil.attacker")

        # When the token is verified
        # Then it is rejected
        with pytest.raises(UnprocessableEntityError):
            await verify_provider_token(
                provider=IdentityProvider.APPLE,
                token=token,
                additional_audiences=["com.legit.app"],
            )

    async def test_both_lists_empty_fails_closed(
        self, mocker: MockerFixture, rsa_keypair: tuple[Any, dict[str, Any]]
    ) -> None:
        """Verify the provider is disabled when both the env list and additional are empty."""
        # Given both sources are empty
        mocker.patch.object(settings.oauth, "apple_audiences", [])
        token = _sign_token(rsa_keypair[0])

        # When the token is verified with no additional audiences
        # Then it fails closed
        with pytest.raises(UnprocessableEntityError):
            await verify_provider_token(
                provider=IdentityProvider.APPLE,
                token=token,
                additional_audiences=[],
            )

    async def test_additional_provided_env_empty_passes(
        self, mocker: MockerFixture, rsa_keypair: tuple[Any, dict[str, Any]]
    ) -> None:
        """Verify a token is accepted when additional_audiences is supplied and env is empty."""
        # Given the env list is empty but the developer registered their audience
        mocker.patch.object(settings.oauth, "apple_audiences", [])
        token = _sign_token(rsa_keypair[0], aud=AUDIENCE)

        # When the token is verified with additional_audiences containing the aud
        identity = await verify_provider_token(
            provider=IdentityProvider.APPLE,
            token=token,
            additional_audiences=[AUDIENCE],
        )

        # Then it resolves successfully
        assert identity.provider_id == "apple-sub-001"


class TestDiscordVerification:
    """Test Discord access token verification."""

    @staticmethod
    def _mock_discord(mocker: MockerFixture, *, status: int = 200) -> None:
        """Patch httpx.AsyncClient for the Discord profile call."""
        response = mocker.Mock(status_code=status)
        response.json.return_value = {
            "id": "123456789010111213",
            "username": "someusername",
            "global_name": "Some User",
            "avatar": "abc123",
            "discriminator": "0",
            "email": "discord@example.com",
            "verified": True,
        }
        if status != 200:
            error_response = mocker.Mock(status_code=status)
            response.raise_for_status = mocker.Mock(
                side_effect=httpx.HTTPStatusError(
                    message="HTTP error",
                    request=mocker.Mock(),
                    response=error_response,
                )
            )
        else:
            response.raise_for_status = mocker.Mock()

        mock_client = mocker.AsyncMock()
        mock_client.get.return_value = response
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=False)
        mocker.patch("vapi.utils.identity.httpx.AsyncClient", return_value=mock_client)

    async def test_valid_discord_token(self, mocker: MockerFixture) -> None:
        """Verify a valid Discord access token resolves with a verified email."""
        # Given Discord returns a profile for the token
        self._mock_discord(mocker)

        # When the token is verified
        identity = await verify_provider_token(
            provider=IdentityProvider.DISCORD,
            token="valid-access-token",  # noqa: S106
        )

        # Then the identity matches the existing discord_profile shape
        assert identity.provider == "discord"
        assert identity.provider_id == "123456789010111213"
        assert identity.email == "discord@example.com"
        assert identity.email_verified is True
        assert identity.profile["avatar_id"] == "abc123"
        assert identity.profile["id"] == "123456789010111213"

    async def test_rejected_discord_token(self, mocker: MockerFixture) -> None:
        """Verify a rejected Discord token raises 422."""
        # Given Discord returns 401 for the token
        self._mock_discord(mocker, status=401)

        # When the token is verified
        # Then verification fails
        with pytest.raises(UnprocessableEntityError):
            await verify_provider_token(provider=IdentityProvider.DISCORD, token="bad")  # noqa: S106

    async def test_discord_unreachable(self, mocker: MockerFixture) -> None:
        """Verify a Discord outage raises 503."""
        # Given Discord times out
        mock_client = mocker.AsyncMock()
        mock_client.get.side_effect = httpx.ConnectTimeout("timeout")
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=False)
        mocker.patch("vapi.utils.identity.httpx.AsyncClient", return_value=mock_client)

        # When the token is verified
        # Then the outage surfaces as 503
        with pytest.raises(ServiceUnavailableError):
            await verify_provider_token(provider=IdentityProvider.DISCORD, token="any")  # noqa: S106


class TestGitHubVerification:
    """Test GitHub access token verification."""

    @staticmethod
    def _mock_github(
        mocker: MockerFixture,
        *,
        user_status: int = 200,
        emails_status: int = 200,
        emails: list[dict[str, Any]] | None = None,
    ) -> None:
        """Patch httpx.AsyncClient for the two GitHub API calls."""
        user_response = mocker.Mock(status_code=user_status)
        user_response.json.return_value = {"id": 4242, "login": "octocat", "email": None}
        if user_status != 200:
            # Simulate raise_for_status raising for non-2xx responses
            error_response = mocker.Mock(status_code=user_status)
            user_response.raise_for_status = mocker.Mock(
                side_effect=httpx.HTTPStatusError(
                    message="HTTP error",
                    request=mocker.Mock(),
                    response=error_response,
                )
            )
        else:
            user_response.raise_for_status = mocker.Mock()
        emails_response = mocker.Mock(status_code=emails_status)
        emails_response.json.return_value = (
            emails
            if emails is not None
            else [
                {"email": "octo@example.com", "primary": True, "verified": True},
                {"email": "other@example.com", "primary": False, "verified": True},
            ]
        )

        mock_client = mocker.AsyncMock()
        mock_client.get.side_effect = [user_response, emails_response]
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=False)
        mocker.patch("vapi.utils.identity.httpx.AsyncClient", return_value=mock_client)

    async def test_valid_github_token(self, mocker: MockerFixture) -> None:
        """Verify a valid GitHub token resolves with the verified primary email."""
        # Given GitHub returns a user and a verified primary email
        self._mock_github(mocker)

        # When the token is verified
        identity = await verify_provider_token(provider=IdentityProvider.GITHUB, token="gho_x")  # noqa: S106

        # Then the identity uses the verified primary email and string id
        assert identity.provider == "github"
        assert identity.provider_id == "4242"
        assert identity.email == "octo@example.com"
        assert identity.email_verified is True
        assert identity.profile["login"] == "octocat"

    async def test_github_no_email_scope(self, mocker: MockerFixture) -> None:
        """Verify a token without the user:email scope yields an unverified fallback."""
        # Given the emails endpoint returns 403 (no user:email scope granted)
        # The 403 status means the email list is never read; only the public profile email is used
        self._mock_github(mocker, emails_status=403)

        # When the token is verified
        identity = await verify_provider_token(provider=IdentityProvider.GITHUB, token="gho_x")  # noqa: S106

        # Then no verified email is claimed
        assert identity.email is None
        assert identity.email_verified is False

    async def test_rejected_github_token(self, mocker: MockerFixture) -> None:
        """Verify a rejected GitHub token raises 422."""
        # Given GitHub returns 401 for the user call
        self._mock_github(mocker, user_status=401)

        # When the token is verified
        # Then verification fails
        with pytest.raises(UnprocessableEntityError):
            await verify_provider_token(provider=IdentityProvider.GITHUB, token="bad")  # noqa: S106

    async def test_github_unreachable(self, mocker: MockerFixture) -> None:
        """Verify a GitHub network failure raises 503."""
        # Given GitHub is unreachable
        mock_client = mocker.AsyncMock()
        mock_client.get.side_effect = httpx.ConnectTimeout("timeout")
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=False)
        mocker.patch("vapi.utils.identity.httpx.AsyncClient", return_value=mock_client)

        # When the token is verified
        # Then the outage surfaces as 503
        with pytest.raises(ServiceUnavailableError):
            await verify_provider_token(provider=IdentityProvider.GITHUB, token="any")  # noqa: S106

    async def test_github_rate_limited(self, mocker: MockerFixture) -> None:
        """Verify a GitHub 403 (rate limit) raises 503, not 422."""
        # Given GitHub returns 403 for the user call
        self._mock_github(mocker, user_status=403)

        # When the token is verified
        # Then the rate-limit surfaces as a provider outage, not a token rejection
        with pytest.raises(ServiceUnavailableError):
            await verify_provider_token(provider=IdentityProvider.GITHUB, token="gho_x")  # noqa: S106

    async def test_github_emails_endpoint_outage(self, mocker: MockerFixture) -> None:
        """Verify a 5xx from the GitHub emails endpoint raises 503 instead of silently skipping verified-email matching."""
        # Given the user endpoint succeeds but the emails endpoint returns 500
        self._mock_github(mocker, emails_status=500)

        # When the token is verified
        # Then the server error surfaces as a provider outage
        with pytest.raises(ServiceUnavailableError):
            await verify_provider_token(provider=IdentityProvider.GITHUB, token="gho_x")  # noqa: S106
