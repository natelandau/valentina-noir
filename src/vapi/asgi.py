"""ASGI application."""

from __future__ import annotations

from litestar import Litestar

from vapi.config import settings
from vapi.server.core import ApplicationCore


def create_app() -> Litestar:
    """Create ASGI application."""
    # Litestar builds the app router from this constructor argument; setting
    # request_max_body_size on AppConfig in a plugin's on_app_init has no effect.
    return Litestar(
        plugins=[ApplicationCore()],
        request_max_body_size=settings.server.request_max_body_size,
    )
