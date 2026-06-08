"""Tests for identity verification settings."""

import pytest

from vapi.config.base import OAuthSettings, StoresSettings


class TestIdentitySettings:
    """Test identity verification settings defaults."""

    def test_identity_settings_defaults(self) -> None:
        """Verify identity verification settings exist with safe defaults."""
        # Given isolated settings instances with no env overrides
        oauth = OAuthSettings()
        stores = StoresSettings()

        # When the identity verification settings are read

        # Then audience allowlists default to empty (providers fail closed)
        assert oauth.apple_audiences == []
        assert oauth.google_audiences == []

        # Then HTTP timeout and JWKS cache TTL have sane defaults
        assert oauth.identity_http_timeout == 10.0
        assert oauth.jwks_cache_ttl == 21600

        # Then the JWKS store key is defined
        assert stores.jwks_key == "jwks"


class TestAudienceParsing:
    """Test audience allowlist parsing accepts multiple input formats."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("com.example.app", ["com.example.app"]),
            ("a.com, b.com ,c.com", ["a.com", "b.com", "c.com"]),
            ("", []),
            ("   ", []),
            ('["a.com", "b.com"]', ["a.com", "b.com"]),  # legacy JSON-array form
            (None, []),
            (["a.com"], ["a.com"]),
        ],
    )
    def test_parse_audiences_formats(
        self, raw: str | list[str] | None, expected: list[str]
    ) -> None:
        """Verify audiences parse from comma-separated, JSON-array, list, and empty inputs."""
        # Given a raw audience value in one of the supported formats

        # When the OAuth settings parse the value
        result = OAuthSettings.parse_audiences(raw)

        # Then the value is normalized to a list of strings
        assert result == expected
