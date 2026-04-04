"""ASGI application."""

from __future__ import annotations

from litestar import Litestar

from vapi.server.core import ApplicationCore


def create_app() -> Litestar:
    """Create ASGI application."""
    return Litestar(plugins=[ApplicationCore()])
