"""Tests for LoggingSettings.log_fields catalog validation."""

import pytest
from pydantic import ValidationError

from vapi.config.base import LoggingSettings


def test_valid_log_fields_accepted() -> None:
    """Verify a list of known catalog fields is stored unchanged."""
    # Given a list of fields all present in the catalog
    fields = ["path", "method", "request_body", "status_code", "duration_ms"]
    # When LoggingSettings is constructed
    settings = LoggingSettings(log_fields=fields)
    # Then the fields are stored unchanged
    assert settings.log_fields == fields


def test_unknown_log_field_rejected() -> None:
    """Verify an unknown field name raises a validation error naming it."""
    # Given a list containing a field not in the catalog
    fields = ["path", "bogus_field"]
    # When / Then constructing settings raises a ValidationError naming the unknown field
    with pytest.raises(ValidationError, match="bogus_field"):
        LoggingSettings(log_fields=fields)


def test_default_log_fields_excludes_request_body() -> None:
    """Verify the default omits the request body but includes duration."""
    # Given no explicit log_fields configuration
    # When LoggingSettings is constructed with defaults
    settings = LoggingSettings()
    # Then the request body is not logged by default but duration is
    assert "request_body" not in settings.log_fields
    assert "duration_ms" in settings.log_fields


def test_default_log_exceptions_is_always() -> None:
    """Verify uncaught exceptions are logged in every environment, not only under debug."""
    # Given default logging settings
    # When LoggingSettings is constructed with defaults
    settings = LoggingSettings()
    # Then exception logging is always on (not gated on app.debug)
    assert settings.log_exceptions == "always"


@pytest.mark.parametrize(
    ("field_a", "field_b"),
    [
        ("request_id", "developer_id"),
        ("error_type", "error_detail"),
    ],
    ids=["correlation-facets", "error-facets"],
)
def test_default_log_fields_include_pair(field_a: str, field_b: str) -> None:
    """Verify both fields in each pair are present in the default log_fields."""
    # Given no explicit log_fields configuration
    # When LoggingSettings is constructed with defaults
    settings = LoggingSettings()
    # Then both fields are enabled out of the box
    assert field_a in settings.log_fields
    assert field_b in settings.log_fields
