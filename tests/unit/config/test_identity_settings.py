"""Tests for identity verification settings."""

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
