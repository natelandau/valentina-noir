"""Tests for shared config parsing in base settings."""

import pytest
from pydantic import BaseModel

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

    @pytest.mark.parametrize(
        ("model", "field", "raw", "expected"),
        [
            (OAuthSettings, "apple_audiences", "com.a.app, com.b.app", ["com.a.app", "com.b.app"]),
            (
                CORSSettings,
                "allowed_origins",
                "https://a.com,https://b.com",
                ["https://a.com", "https://b.com"],
            ),
            (
                AllowedHostsSettings,
                "hosts",
                "a.example.com,b.example.com",
                ["a.example.com", "b.example.com"],
            ),
            (LoggingSettings, "obfuscate_headers", "X-Foo,X-Bar", {"X-Foo", "X-Bar"}),
        ],
    )
    def test_collection_field_accepts_csv(
        self,
        model: type[BaseModel],
        field: str,
        raw: str,
        expected: list[str] | set[str],
    ) -> None:
        """Verify NoDecode collection fields parse a comma-separated string into a collection."""
        # Given a collection field supplied as a comma-separated string
        # When the settings model is built
        settings = model(**{field: raw})

        # Then the value is parsed into the expected list or set
        assert getattr(settings, field) == expected

    def test_log_fields_csv_still_validated_against_catalog(self) -> None:
        """Verify the catalog validator still runs after comma-separated parsing."""
        # Given a comma-separated log_fields value containing an unknown field
        # When the logging settings are built
        # Then the catalog after-validator rejects the unknown entry
        with pytest.raises(ValueError, match="Unknown log_fields entries"):
            LoggingSettings(log_fields="path,not_a_real_field")  # type: ignore[arg-type]
