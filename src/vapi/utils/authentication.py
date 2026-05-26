"""Authentication utilities."""

import logging
import secrets
import string
from typing import TYPE_CHECKING

from vapi.constants import REQUEST_ID_STATE_KEY

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection

__all__ = ("generate_api_key", "log_auth_failure")

logger = logging.getLogger("vapi")


def log_auth_failure(connection: "ASGIConnection", reason: str) -> None:
    """Record a rejected authentication attempt at WARNING with request correlation.

    Auth middleware runs outside the combined request logger, so a rejection there produces
    no combined log entry; without this, invalid-credential 401s would be invisible. Logs the
    request_id and path (never the credential) so the failure is observable and correlatable.
    """
    state = connection.scope.get("state")
    request_id = state.get(REQUEST_ID_STATE_KEY) if isinstance(state, dict) else None
    logger.warning(
        "Authentication failed",
        extra={
            "request_id": request_id,
            "path": connection.scope.get("path"),
            "reason": reason,
        },
    )


def generate_api_key(length: int = 32) -> str:
    """Generate an API key.

    Args:
        length (int): The length of the API key.

    Returns:
        str: The generated API key.
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
