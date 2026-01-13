"""Test the cache module."""

from __future__ import annotations

import pytest
from litestar.config.response_cache import default_cache_key_builder
from litestar.testing import RequestFactory

from vapi.constants import AUTH_HEADER_KEY
from vapi.lib.crypt import hmac_sha256_hex
from vapi.lib.stores import response_cache_key_builder
from vapi.server.core import ApplicationCore

pytestmark = pytest.mark.anyio


@pytest.mark.no_clean_db
def test_cache_key_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that the cache key builder is working correctly."""
    api_key = "test"
    api_key_fingerprint = hmac_sha256_hex(data=api_key)

    monkeypatch.setattr(ApplicationCore, "app_slug", "the-slug")
    request = RequestFactory().get("/test", headers={AUTH_HEADER_KEY: api_key})
    default_cache_key = default_cache_key_builder(request)
    assert response_cache_key_builder(request) == f"{api_key_fingerprint}:{default_cache_key}"
