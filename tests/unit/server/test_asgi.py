"""Unit tests for ASGI application assembly."""

import pytest
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


def test_cors_config_carries_allow_and_expose_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the CORS config allows the custom request headers and exposes the response headers."""
    # Given CORS enabled
    monkeypatch.setattr(settings.cors, "enabled", True)

    # When the application is assembled
    app = create_app()
    cors = app.cors_config

    # Then the config carries the new allow and expose headers
    assert cors is not None
    # Litestar lowercases allow_headers but keeps expose_headers as given
    assert {"idempotency-key", "on-behalf-of"} <= set(cors.allow_headers)
    assert {"Retry-After", "X-Request-Id", "RateLimit", "RateLimit-Policy"} <= set(
        cors.expose_headers
    )
