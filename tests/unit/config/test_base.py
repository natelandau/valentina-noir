"""Tests for shared config parsing in base settings."""

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from vapi.config.base import (
    AllowedHostsSettings,
    CORSSettings,
    LoggingSettings,
    OAuthSettings,
    PostgresSettings,
    RateLimitSettings,
    Settings,
    parse_str_collection,
)


def test_settings_ignore_env_secret_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify settings come only from the environment, never from a `.env.secret` file."""
    # Given a `.env.secret` in the working directory that sets a variable the environment does not
    (tmp_path / ".env.secret").write_text("VAPI_DOCKER_MIGRATE=true\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VAPI_DOCKER_MIGRATE", raising=False)

    # When the settings are built
    loaded = Settings()

    # Then the file's value is not applied
    assert loaded.docker_migrate is False


def test_settings_require_postgres_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify settings fail to load when the database password is not set."""
    # Given an environment with no database password
    monkeypatch.delenv("VAPI_POSTGRES__PASSWORD", raising=False)

    # When the settings are built
    with pytest.raises(ValidationError) as exc_info:
        Settings()

    # Then validation names the missing password
    assert ("postgres", "password") in [error["loc"] for error in exc_info.value.errors()]


def test_postgres_settings_have_no_default_password() -> None:
    """Verify the database settings never fall back to a built-in password."""
    # Given no password argument

    # When the database settings are built
    with pytest.raises(ValidationError) as exc_info:
        PostgresSettings()

    # Then validation reports the password as required
    assert [error["loc"] for error in exc_info.value.errors()] == [("password",)]


def test_rate_limit_policies_default_to_hourly_and_burst() -> None:
    """Verify the global rate limits are enforced when no policy is configured."""
    # Given no configured rate limit policies

    # When the rate limit settings are built
    loaded = RateLimitSettings()

    # Then the hourly and burst policies apply
    assert {
        policy.name: (policy.capacity, policy.refill_rate) for policy in loaded.policies.values()
    } == {"hourly": (1000, 0.28), "burst": (60, 1.0)}


def test_rate_limit_policies_from_env_replace_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify configured policies replace the defaults instead of merging with them."""
    # Given one policy configured in the environment
    monkeypatch.setenv("VAPI_RATE_LIMIT__POLICIES__0__NAME", "custom")
    monkeypatch.setenv("VAPI_RATE_LIMIT__POLICIES__0__CAPACITY", "5")
    monkeypatch.setenv("VAPI_RATE_LIMIT__POLICIES__0__REFILL_RATE", "0.1")

    # When the settings are built
    loaded = Settings()

    # Then only the configured policy applies
    assert [policy.name for policy in loaded.rate_limit.policies.values()] == ["custom"]


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
            LoggingSettings(log_fields="path,not_a_real_field")
