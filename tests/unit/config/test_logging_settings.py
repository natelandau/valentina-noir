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


def test_default_log_fields_include_request_and_developer_id() -> None:
    """Verify request_id and developer_id are logged by default for request correlation."""
    # Given no explicit log_fields configuration
    # When LoggingSettings is constructed with defaults
    settings = LoggingSettings()
    # Then both correlation facets are enabled out of the box
    assert "request_id" in settings.log_fields
    assert "developer_id" in settings.log_fields


def test_default_log_fields_include_error_facets() -> None:
    """Verify error_type and error_detail are logged by default so failures explain themselves."""
    # Given no explicit log_fields configuration
    # When LoggingSettings is constructed with defaults
    settings = LoggingSettings()
    # Then the error facets are enabled out of the box (absent on successful requests)
    assert "error_type" in settings.log_fields
    assert "error_detail" in settings.log_fields
