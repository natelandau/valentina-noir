"""Developer services."""

from vapi.db.sql_models.developer import Developer
from vapi.lib.crypt import CryptService, hmac_sha256_hex
from vapi.utils.authentication import generate_api_key
from vapi.utils.time import time_now

_crypt_service = CryptService()


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
