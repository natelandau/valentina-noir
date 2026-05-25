"""Test the server log entry DTO."""

import json

from vapi.domain.services.server_log_dto import LogEntry


def test_log_entry_from_line_parses_known_and_extra_fields() -> None:
    """Verify a valid JSON line maps known keys and collects the rest into extra."""
    # Given a JSON log line with standard and structured-extra fields
    line = json.dumps(
        {
            "level": "WARNING",
            "timestamp": "2026-05-25T10:00:00Z",
            "name": "vapi",
            "message": "something happened",
            "exception": None,
            "request_id": "abc-123",
            "status": 503,
        }
    )

    # When parsing the line
    entry = LogEntry.from_line(line)

    # Then known fields are mapped and unknown keys land in extra
    assert entry.level == "WARNING"
    assert entry.timestamp == "2026-05-25T10:00:00Z"
    assert entry.name == "vapi"
    assert entry.message == "something happened"
    assert entry.exception is None
    assert entry.raw is None
    assert entry.extra == {"request_id": "abc-123", "status": 503}


def test_log_entry_from_line_non_dict_json_returns_raw() -> None:
    """Verify a JSON value that is not an object is preserved as raw."""
    # Given a line that is valid JSON but not an object
    line = '"just a string"'

    # When parsing the line
    entry = LogEntry.from_line(line)

    # Then the raw text is preserved and parsed fields are None
    assert entry.raw == '"just a string"'
    assert entry.level is None
    assert entry.extra == {}


def test_log_entry_from_line_unparsable_returns_raw() -> None:
    """Verify a non-JSON line is preserved in the raw field with no parsed values."""
    # Given a line that is not valid JSON
    line = "this is not json"

    # When parsing the line
    entry = LogEntry.from_line(line)

    # Then the raw text is preserved and parsed fields are None
    assert entry.raw == "this is not json"
    assert entry.level is None
    assert entry.message is None
    assert entry.extra == {}


def test_log_entry_from_line_coerces_non_string_known_fields() -> None:
    """Verify non-string values in known fields are coerced to strings."""
    # Given a JSON line whose level and name are numeric (the formatter can emit this
    # when a logged message contains a `key=<number>` token)
    line = json.dumps({"level": 42, "name": 7, "message": "x"})

    # When parsing the line
    entry = LogEntry.from_line(line)

    # Then the known fields are coerced to str, preserving the str|None contract
    assert entry.level == "42"
    assert entry.name == "7"
    assert entry.message == "x"


def test_log_entry_from_line_coerces_non_string_exception() -> None:
    """Verify a non-string exception value is coerced to a string."""
    # Given a JSON line whose exception field is a list
    line = json.dumps({"level": "ERROR", "exception": ["frame1", "frame2"]})

    # When parsing the line
    entry = LogEntry.from_line(line)

    # Then exception is a string, not a list
    assert isinstance(entry.exception, str)
