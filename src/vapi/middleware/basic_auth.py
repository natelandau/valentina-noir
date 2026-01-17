"""HTTP Basic Auth middleware for SAQ admin interface."""

from __future__ import annotations

import base64
import logging
import secrets
from typing import TYPE_CHECKING

from litestar.exceptions import NotAuthorizedException
from litestar.middleware import DefineMiddleware
from litestar.middleware.authentication import (
    AbstractAuthenticationMiddleware,
    AuthenticationResult,
)

from vapi.config import settings

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection

logger = logging.getLogger("vapi")


class BasicAuthMiddleware(AbstractAuthenticationMiddleware):
    """HTTP Basic Auth middleware for admin routes."""

    async def authenticate_request(self, connection: ASGIConnection) -> AuthenticationResult:
        """Authenticate request using HTTP Basic Auth for /saq/ paths only."""
        path = connection.scope.get("path", "")

        # Skip authentication for non-SAQ paths - let other middleware handle them
        if not path.startswith("/saq"):
            return AuthenticationResult(user=None, auth=None)

        auth_header = connection.headers.get("Authorization", "")

        if not auth_header.startswith("Basic "):
            raise NotAuthorizedException(
                detail="Authentication required",
                headers={"WWW-Authenticate": 'Basic realm="SAQ Admin"'},
            )

        try:
            encoded_credentials = auth_header.split(" ", 1)[1]
            decoded = base64.b64decode(encoded_credentials).decode("utf-8")
            username, _, password = decoded.partition(":")
        except (ValueError, UnicodeDecodeError) as e:
            msg = f"Invalid Basic Auth header: {e}"
            logger.warning(msg)
            raise NotAuthorizedException(
                detail="Invalid credentials format",
                headers={"WWW-Authenticate": 'Basic realm="SAQ Admin"'},
            ) from e

        # Use constant-time comparison to prevent timing attacks
        valid_username = settings.saq.admin_username or ""
        valid_password = settings.saq.admin_password or ""

        username_matches = secrets.compare_digest(username, valid_username)
        password_matches = secrets.compare_digest(password, valid_password)

        if not (username_matches and password_matches) or not valid_username:
            raise NotAuthorizedException(
                detail="Invalid credentials",
                headers={"WWW-Authenticate": 'Basic realm="SAQ Admin"'},
            )

        return AuthenticationResult(user={"username": username, "is_admin": True}, auth=username)


# Only apply to /saq/ paths
basic_auth_mw = DefineMiddleware(BasicAuthMiddleware)
