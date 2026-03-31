"""ASGI application."""

from __future__ import annotations

from litestar import Litestar

from vapi.server.core import ApplicationCore
from vapi.server.tortoise_plugin import TortoisePlugin


def create_app() -> Litestar:
    """Create ASGI application."""
    return Litestar(plugins=[ApplicationCore(), TortoisePlugin()])
