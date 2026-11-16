"""Developer services."""

from typing import TYPE_CHECKING

import msgspec
from tortoise.transactions import in_transaction

from vapi.db.sql_models.developer import Developer
from vapi.lib.crypt import CryptService, hmac_sha256_hex
from vapi.lib.exceptions import NotAuthorizedError, NotFoundError, ValidationError
from vapi.lib.patch import apply_patch
from vapi.utils.authentication import generate_api_key
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from vapi.domain.controllers.developer.dto import DeveloperPatch
    from vapi.domain.controllers.global_admin.dto import AdminDeveloperPatch

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

    async def generate_api_key(
        self, developer: Developer, *, expected_fingerprint: str | None = None
    ) -> str:
        """Generate and persist a new API key for the given developer.

        Use when the caller needs only the plaintext key. See ``rotate_api_key``.

        Args:
            developer: The Developer instance to update.
            expected_fingerprint: Fingerprint of the key the caller authenticated with.

        Returns:
            The plaintext API key (only available at generation time).
        """
        api_key, _ = await self.rotate_api_key(developer, expected_fingerprint=expected_fingerprint)
        return api_key

    async def rotate_api_key(
        self, developer: Developer, *, expected_fingerprint: str | None = None
    ) -> tuple[str, str | None]:
        """Generate and persist a new API key and report the fingerprint it replaced.

        Hashes the key with argon2 and stores an HMAC-SHA256 fingerprint for
        fast lookup without exposing the plaintext key. Writes only the key
        columns, so a concurrent change to any other column is kept. The replaced
        fingerprint is read under the row lock, so evicting it from the
        authentication cache revokes the key that was actually live.

        Args:
            developer: The Developer instance to update.
            expected_fingerprint: Fingerprint of the key the caller authenticated with,
                when developers rotate their own key. The rotation is refused if the
                stored key no longer matches, so it cannot replace an admin-issued key.

        Returns:
            The plaintext API key (only available at generation time) and the
            fingerprint of the key it replaced.
        """
        api_key = generate_api_key()
        hashed_api_key = await _crypt_service.hash(api_key)

        async with in_transaction():
            await self._lock_active_developer(developer, expected_fingerprint=expected_fingerprint)
            previous_fingerprint = developer.api_key_fingerprint
            developer.hashed_api_key = hashed_api_key
            developer.api_key_fingerprint = hmac_sha256_hex(data=api_key)
            developer.key_generated = time_now()
            await developer.save(
                update_fields=["hashed_api_key", "api_key_fingerprint", "key_generated"]
            )
        return api_key, previous_fingerprint

    async def update(
        self,
        developer: Developer,
        data: "DeveloperPatch | AdminDeveloperPatch",
        *,
        expected_fingerprint: str | None = None,
    ) -> dict[str, dict[str, object]]:
        """Apply a patch to a developer without overwriting concurrent changes.

        The patch is diffed against the row as locked, not as loaded, and only the
        changed columns are written, so the edit cannot restore an archive flag,
        global-admin flag, or API key changed after ``developer`` was loaded.

        Args:
            developer: The Developer instance to update. Refreshed from the database.
            data: The patch payload; only non-UNSET fields are applied.
            expected_fingerprint: Fingerprint of the key the caller authenticated with,
                when developers edit their own record. The edit is refused if the stored
                key no longer matches.

        Returns:
            A diff of the changed fields for audit logging.
        """
        if not isinstance(data.provider_audiences, msgspec.UnsetType):
            validate_provider_audiences(data.provider_audiences)

        async with in_transaction():
            await self._lock_active_developer(developer, expected_fingerprint=expected_fingerprint)
            changes = apply_patch(developer, data)
            if changes:
                await developer.save(update_fields=list(changes))
        return changes

    async def archive(self, developer: Developer) -> None:
        """Archive a developer, refreshing it so its live key fingerprint can be evicted.

        Args:
            developer: The Developer instance to archive. Refreshed from the database.
        """
        async with in_transaction():
            await self._lock_active_developer(developer)
            developer.is_archived = True
            await developer.save(update_fields=["is_archived"])

    @staticmethod
    async def _lock_active_developer(
        developer: Developer, *, expected_fingerprint: str | None = None
    ) -> None:
        """Lock the developer's row inside the caller's transaction and reload ``developer``.

        With ``expected_fingerprint``, the row must also still hold that key fingerprint.

        Raises:
            NotAuthorizedError: When ``expected_fingerprint`` is given and the row is
                missing, archived, or holds another key.
            NotFoundError: When no ``expected_fingerprint`` is given and the row is
                missing or archived.
        """
        filters: dict[str, object] = {"is_archived": False}
        if expected_fingerprint is not None:
            filters["api_key_fingerprint"] = expected_fingerprint
        if await developer.lock_for_update(**filters):
            return
        if expected_fingerprint is not None:
            raise NotAuthorizedError(detail="API key is no longer valid")
        raise NotFoundError(detail="Developer not found")

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
