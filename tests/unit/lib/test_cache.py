"""Test the cache module."""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

import pytest
from litestar.config.response_cache import default_cache_key_builder
from litestar.testing import RequestFactory

from vapi.constants import AUTH_HEADER_KEY, ON_BEHALF_OF_HEADER_KEY
from vapi.lib.crypt import hmac_sha256_hex
from vapi.lib.stores import response_cache_key_builder
from vapi.server.core import ApplicationCore

if TYPE_CHECKING:
    from litestar import Litestar, Request
    from litestar.types import RouteHandlerType

pytestmark = pytest.mark.anyio


def test_cache_key_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the cache key combines the API key fingerprint and acting user."""
    # Given a request with an API key but no On-Behalf-Of header
    api_key = "test"
    api_key_fingerprint = hmac_sha256_hex(data=api_key)
    monkeypatch.setattr(ApplicationCore, "app_slug", "the-slug")
    request = RequestFactory().get("/test", headers={AUTH_HEADER_KEY: api_key})

    # When the cache key is built
    default_cache_key = default_cache_key_builder(request)

    # Then it includes an empty, length-prefixed acting-user segment before the default key
    assert response_cache_key_builder(request) == f"{api_key_fingerprint}:0::{default_cache_key}"


def test_cache_key_builder_varies_by_acting_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the cache key differs per acting user so role-filtered responses don't leak."""
    # Given two requests sharing an API key but acting on behalf of different users
    api_key = "test"
    monkeypatch.setattr(ApplicationCore, "app_slug", "the-slug")
    request_player = RequestFactory().get(
        "/test", headers={AUTH_HEADER_KEY: api_key, ON_BEHALF_OF_HEADER_KEY: "player-uuid"}
    )
    request_storyteller = RequestFactory().get(
        "/test", headers={AUTH_HEADER_KEY: api_key, ON_BEHALF_OF_HEADER_KEY: "storyteller-uuid"}
    )

    # When cache keys are built for each
    key_player = response_cache_key_builder(request_player)
    key_storyteller = response_cache_key_builder(request_storyteller)

    # Then the keys differ, so one user cannot receive another user's cached response
    assert key_player != key_storyteller
    assert "player-uuid" in key_player
    assert "storyteller-uuid" in key_storyteller


@cache
def _app_and_list_characters_handler() -> tuple[Litestar, RouteHandlerType]:
    """Build the app once and find its cached list-characters handler."""
    from vapi.asgi import create_app

    app = create_app()
    handler = next(
        h
        for route in app.routes
        for h in getattr(route, "route_handlers", [])
        if h.operation_id == "listCharacters"
    )
    return app, handler


def _list_characters_request(query: dict[str, str | list[str]]) -> Request:
    """Build a request routed to the cached list-characters handler."""
    app, handler = _app_and_list_characters_handler()
    company_id = "11111111-1111-1111-1111-111111111111"
    return RequestFactory(app=app).get(
        f"/api/v1/companies/{company_id}/characters",
        headers={AUTH_HEADER_KEY: "test", ON_BEHALF_OF_HEADER_KEY: "user-uuid"},
        query_params=query,
        path_params={"company_id": company_id},
        route_handler=handler,
    )


def test_cache_key_ignores_undeclared_query_params() -> None:
    """Verify query params the handler does not declare cannot mint new cache entries."""
    # Given two requests to a cached list route that differ only in an unknown param
    plain = _list_characters_request({"limit": "100"})
    padded = _list_characters_request({"limit": "100", "bust": "1"})

    # When cache keys are built for each
    # Then they are equal, so the second request reuses the first entry
    assert response_cache_key_builder(padded) == response_cache_key_builder(plain)


def test_cache_key_varies_by_declared_query_params() -> None:
    """Verify declared query params still separate cache entries."""
    # Given two requests to a cached list route with different page sizes
    small = _list_characters_request({"limit": "10"})
    large = _list_characters_request({"limit": "100"})

    # When cache keys are built for each
    # Then they differ
    assert response_cache_key_builder(small) != response_cache_key_builder(large)


def test_cache_key_ignores_repeated_scalar_query_params() -> None:
    """Verify repeating a scalar param keys on the value the handler reads, the last one."""
    # Given a request with one limit and one that repeats limit with a junk value first
    plain = _list_characters_request({"limit": "100"})
    padded = _list_characters_request({"limit": ["junk", "100"]})

    # When cache keys are built for each
    # Then they are equal
    assert response_cache_key_builder(padded) == response_cache_key_builder(plain)


def test_cache_key_builder_keeps_colon_bearing_acting_users_apart() -> None:
    """Verify a ':' in On-Behalf-Of cannot make two acting users and paths share a key."""
    # Given two requests whose acting user and path differ only in where ":GET" falls
    first = RequestFactory().get("/a:GET/b", headers={ON_BEHALF_OF_HEADER_KEY: "user"})
    second = RequestFactory().get("/b", headers={ON_BEHALF_OF_HEADER_KEY: "user:GET/a"})

    # When building their cache keys / Then they differ
    assert response_cache_key_builder(first) != response_cache_key_builder(second)
