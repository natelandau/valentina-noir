"""Test the cache module."""

from __future__ import annotations

import pytest
from litestar.config.response_cache import default_cache_key_builder
from litestar.testing import RequestFactory

from vapi.constants import AUTH_HEADER_KEY, ON_BEHALF_OF_HEADER_KEY
from vapi.lib.crypt import hmac_sha256_hex
from vapi.lib.stores import response_cache_key_builder
from vapi.server.core import ApplicationCore

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

    # Then it includes an empty acting-user segment between fingerprint and default key
    assert response_cache_key_builder(request) == f"{api_key_fingerprint}::{default_cache_key}"


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
