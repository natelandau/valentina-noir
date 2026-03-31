"""Crypt utilities."""

from __future__ import annotations

import asyncio
import base64
import hmac
from hashlib import sha256

from passlib.context import CryptContext

from vapi.config import settings

__all__ = (
    "CryptService",
    "get_encryption_key",
    "get_password_hash",
    "hmac_sha256_hex",
    "verify_password",
)


password_crypt_context = CryptContext(schemes=["argon2"], deprecated="auto")


def get_encryption_key(secret: str) -> bytes:
    """Get Encryption Key.

    Args:
        secret (str): Secret key used for encryption

    Returns:
        bytes: a URL safe encoded version of secret
    """
    if len(secret) <= 32:  # noqa: PLR2004
        secret = f"{secret:<32}"[:32]
    return base64.urlsafe_b64encode(secret.encode())


async def get_password_hash(password: str | bytes) -> str:
    """Get password hash.

    Args:
        password: Plain password
    Returns:
        str: Hashed password
    """
    return await asyncio.get_running_loop().run_in_executor(
        None, password_crypt_context.hash, password
    )


async def verify_password(plain_password: str | bytes, hashed_password: str) -> bool:
    """Verify Password.

    Args:
        plain_password (str | bytes): The string or byte password
        hashed_password (str): the hash of the password

    Returns:
        bool: True if password matches hash.
    """
    valid, _ = await asyncio.get_running_loop().run_in_executor(
        None,
        password_crypt_context.verify_and_update,
        plain_password,
        hashed_password,
    )
    return bool(valid)


class CryptService:
    """Thin async wrapper around the module-level CryptContext.

    Instantiated as a class variable on models (before the event loop starts),
    so the constructor must not reference the running loop.
    """

    async def hash(self, secret: str) -> str:
        """Hash a secret using argon2, offloaded to a thread pool."""
        return await asyncio.get_running_loop().run_in_executor(
            None, password_crypt_context.hash, secret
        )

    async def verify(self, secret: str, hash_: str) -> bool:
        """Verify a secret against an argon2 hash, offloaded to a thread pool."""
        return await asyncio.get_running_loop().run_in_executor(
            None, password_crypt_context.verify, secret, hash_
        )


def hmac_sha256_hex(data: str | bytes) -> str:
    """Compute HMAC-SHA256 and return lowercase hex digest.

    Use to derive deterministic, non-reversible fingerprints for secrets such as API keys.
    """
    secret = settings.authentication_encryption_key
    key_bytes = secret.encode("utf-8")
    data_bytes = data if isinstance(data, (bytes, bytearray)) else data.encode("utf-8")
    return hmac.new(key_bytes, data_bytes, sha256).hexdigest()
