"""Authentication utilities."""

import secrets
import string

__all__ = ("generate_api_key",)


def generate_api_key(length: int = 32) -> str:
    """Generate an API key.

    Args:
        length (int): The length of the API key.

    Returns:
        str: The generated API key.
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
