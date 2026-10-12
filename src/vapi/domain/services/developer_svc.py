"""Developer services."""

from vapi.db.sql_models.developer import Developer
from vapi.lib.crypt import CryptService, hmac_sha256_hex
from vapi.lib.exceptions import ValidationError
from vapi.utils.authentication import generate_api_key
from vapi.utils.time import time_now

_crypt_service = CryptService()

_ALLOWED_AUDIENCE_PROVIDERS = frozenset({"apple", "google"})
_MAX_AUDIENCES_PER_PROVIDER = 20
_MAX_AUDIENCE_LENGTH = 255


def validate_provider_audiences(value: object) -> None:
    """Raise ValidationError if provider_audiences fails structural or content constraints.

    Only "apple" and "google" keys are accepted; values must be lists of non-empty,
    non-whitespace strings up to 255 chars each, with at most 20 entries per provider.
    Call this before writing provider_audiences to a Developer record so that
    jwt.decode always receives well-formed audience values.

    Args:
        value: The raw value from the patch payload.
    """
    if value is None:
        return

    if not isinstance(value, dict):
        raise ValidationError(
            detail="provider_audiences must be a JSON object mapping provider names to audience lists",
            invalid_parameters=[
                {"field": "provider_audiences", "message": "Must be an object"},
            ],
        )

    invalid_keys = sorted(set(value.keys()) - _ALLOWED_AUDIENCE_PROVIDERS)
    if invalid_keys:
        raise ValidationError(
            detail=f"provider_audiences contains unsupported provider keys: {invalid_keys}",
            invalid_parameters=[
                {
                    "field": "provider_audiences",
                    "message": f"Keys must be one of: apple, google. Got: {invalid_keys}",
                },
            ],
        )

    for provider, audiences in value.items():
        if not isinstance(audiences, list):
            raise ValidationError(
                detail=f"provider_audiences[{provider!r}] must be a list of strings",
                invalid_parameters=[
                    {
                        "field": f"provider_audiences.{provider}",
                        "message": "Value must be a list of strings",
                    },
                ],
            )

        if len(audiences) > _MAX_AUDIENCES_PER_PROVIDER:
            raise ValidationError(
                detail=f"provider_audiences[{provider!r}] exceeds the maximum of {_MAX_AUDIENCES_PER_PROVIDER} entries",
                invalid_parameters=[
                    {
                        "field": f"provider_audiences.{provider}",
                        "message": f"At most {_MAX_AUDIENCES_PER_PROVIDER} audiences per provider are allowed",
                    },
                ],
            )

        for i, aud in enumerate(audiences):
            # Reject non-strings and whitespace-only strings; both are
            # semantically invalid audience identifiers for jwt.decode
            if not isinstance(aud, str) or not aud.strip():
                raise ValidationError(
                    detail=f"provider_audiences[{provider!r}][{i}] must be a non-empty string",
                    invalid_parameters=[
                        {
                            "field": f"provider_audiences.{provider}[{i}]",
                            "message": "Each audience must be a non-empty string",
                        },
                    ],
                )

            if len(aud) > _MAX_AUDIENCE_LENGTH:
                raise ValidationError(
                    detail=f"provider_audiences[{provider!r}][{i}] exceeds the maximum length of {_MAX_AUDIENCE_LENGTH} characters",
                    invalid_parameters=[
                        {
                            "field": f"provider_audiences.{provider}[{i}]",
                            "message": f"Each audience must be at most {_MAX_AUDIENCE_LENGTH} characters",
                        },
                    ],
                )


class DeveloperService:
    """Developer service for API key management."""

    async def generate_api_key(self, developer: Developer) -> str:
        """Generate and persist a new API key for the given developer.

        Hashes the key with argon2 and stores an HMAC-SHA256 fingerprint for
        fast lookup without exposing the plaintext key. Returns the plaintext
        key so the caller can present it to the developer once.

        Args:
            developer: The Developer instance to update.

        Returns:
            The plaintext API key (only available at generation time).
        """
        api_key = generate_api_key()
        developer.hashed_api_key = await _crypt_service.hash(api_key)
        developer.api_key_fingerprint = hmac_sha256_hex(data=api_key)
        developer.key_generated = time_now()
        await developer.save()
        return api_key

    async def verify_api_key(self, developer: Developer, api_key: str) -> bool:
        """Verify a plaintext API key against the developer's stored hash.

        Returns False immediately when no key has been generated yet, avoiding
        a hash comparison against a null value.

        Args:
            developer: The Developer instance whose key to verify against.
            api_key: The plaintext API key to verify.

        Returns:
            True if the key matches the stored hash, False otherwise.
        """
        if not developer.hashed_api_key:
            return False
        return await _crypt_service.verify(api_key, developer.hashed_api_key)
