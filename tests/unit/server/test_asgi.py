"""Unit tests for ASGI application assembly."""

from litestar.handlers import HTTPRouteHandler

from vapi.asgi import create_app
from vapi.config import settings


def test_route_handlers_enforce_configured_body_size_limit() -> None:
    """Verify every HTTP route enforces the configured request body size limit."""
    # Given the assembled application
    app = create_app()

    # When resolving each HTTP handler's body size limit
    limits = {
        handler.resolve_request_max_body_size()
        for route in app.routes
        for handler in getattr(route, "route_handlers", [])
        if isinstance(handler, HTTPRouteHandler)
    }

    # Then all of them use the configured setting
    assert limits == {settings.server.request_max_body_size}
