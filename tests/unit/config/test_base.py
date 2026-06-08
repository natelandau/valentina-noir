"""Tests for shared config parsing in base settings."""

import pytest

from vapi.config.base import (
    AllowedHostsSettings,
    CORSSettings,
    LoggingSettings,
    OAuthSettings,
    parse_str_collection,
)


class TestParseStrCollection:
    """Test the comma-separated collection parser."""

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
            ({"a.com"}, ["a.com"]),
        ],
    )
    def test_parse_str_collection_formats(
        self, raw: str | list[str] | set[str] | None, expected: list[str]
    ) -> None:
        """Verify values parse from comma-separated, JSON-array, sequence, and empty inputs."""
        # Given a raw collection value in one of the supported formats

        # When the parser normalizes it
        result = parse_str_collection(raw)

        # Then the result is a list of strings
        assert result == expected


class TestCsvFieldWiring:
    """Test that NoDecode + BeforeValidator are wired onto the collection settings fields."""

    def test_oauth_audiences_accept_csv(self) -> None:
        """Verify OAuth audiences parse from a comma-separated string."""
        # Given audiences supplied as a comma-separated string
        # When the OAuth settings are built
        oauth = OAuthSettings(apple_audiences="com.a.app, com.b.app")  # type: ignore[arg-type]

        # Then the value is split into a list
        assert oauth.apple_audiences == ["com.a.app", "com.b.app"]

    def test_cors_origins_accept_csv(self) -> None:
        """Verify CORS allowed origins parse from a comma-separated string."""
        # Given origins supplied as a comma-separated string
        # When the CORS settings are built
        cors = CORSSettings(allowed_origins="https://a.com,https://b.com")  # type: ignore[arg-type]

        # Then the value is split into a list
        assert cors.allowed_origins == ["https://a.com", "https://b.com"]

    def test_allowed_hosts_accept_csv(self) -> None:
        """Verify allowed hosts parse from a comma-separated string."""
        # Given hosts supplied as a comma-separated string
        # When the allowed-hosts settings are built
        allowed = AllowedHostsSettings(hosts="a.example.com,b.example.com")  # type: ignore[arg-type]

        # Then the value is split into a list
        assert allowed.hosts == ["a.example.com", "b.example.com"]

    def test_obfuscate_headers_accept_csv(self) -> None:
        """Verify the obfuscate-headers set parses from a comma-separated string."""
        # Given header names supplied as a comma-separated string
        # When the logging settings are built
        log = LoggingSettings(obfuscate_headers="X-Foo,X-Bar")  # type: ignore[arg-type]

        # Then the value is parsed into a set
        assert log.obfuscate_headers == {"X-Foo", "X-Bar"}

    def test_log_fields_csv_still_validated_against_catalog(self) -> None:
        """Verify the catalog validator still runs after comma-separated parsing."""
        # Given a comma-separated log_fields value containing an unknown field
        # When the logging settings are built
        # Then the catalog after-validator rejects the unknown entry
        with pytest.raises(ValueError, match="Unknown log_fields entries"):
            LoggingSettings(log_fields="path,not_a_real_field")  # type: ignore[arg-type]
