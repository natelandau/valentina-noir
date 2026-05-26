"""Tests for log formatters and the structured key=value message parser."""

import json
import logging
import sys
from collections.abc import Callable

import pytest

from vapi.lib.log_formatters import (
    ColorFormatter,
    LitestarJsonFormatter,
    StructuredMessageParser,
)


@pytest.fixture
def make_log_record() -> Callable[..., logging.LogRecord]:
    """Build LogRecord instances with overridable level, message, exc_info, and extra attributes."""

    def _make(
        msg: str = "test message",
        *,
        level: int = logging.INFO,
        exc_info: tuple | None = None,
        **extra: object,
    ) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test",
            level=level,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=None,
            exc_info=exc_info,
        )
        for key, value in extra.items():
            setattr(record, key, value)
        return record

    return _make


def _raise_value_error() -> None:
    """Raise a ValueError so callers can capture a real traceback."""
    msg = "boom"
    raise ValueError(msg)


def _capture_exc_info() -> tuple:
    """Capture the exc_info tuple for a raised ValueError, including its traceback."""
    try:
        _raise_value_error()
    except ValueError:
        return sys.exc_info()


def test_parse_extracts_typed_values() -> None:
    """Extract key=value pairs into their natural Python types."""
    # Given a message with mixed key=value pairs
    parser = StructuredMessageParser()
    message = "HTTP Request: path=/v1/x method=POST status_code=200 duration_ms=42"
    # When parsed
    result = parser.parse(message)
    # Then values are extracted with their natural Python types
    assert result["path"] == "/v1/x"
    assert result["method"] == "POST"
    assert result["status_code"] == 200
    assert result["duration_ms"] == 42


def test_parse_handles_collections_quotes_and_literals() -> None:
    """Coerce dict, list, quoted-string, and literal values to the right types."""
    # Given values that are dicts, lists, quoted strings, and literals
    parser = StructuredMessageParser()
    message = 'data={"a": 1} items=[1, 2] name="John" flag=True missing=None'
    # When parsed
    result = parser.parse(message)
    # Then each is coerced to the right type
    assert result["data"] == {"a": 1}
    assert result["items"] == [1, 2]
    assert result["name"] == "John"
    assert result["flag"] is True
    assert result["missing"] is None


def test_parse_coerces_floats_and_python_repr_collections() -> None:
    """Parse float values and fall back to Python-repr syntax for collections."""
    # Given a float value and a Python-repr dict (single quotes, None)
    parser = StructuredMessageParser()
    message = "ratio=3.14 meta={'k': None}"
    # When parsed
    result = parser.parse(message)
    # Then the float is numeric and the repr-style dict is parsed via the literal fallback
    assert result["ratio"] == 3.14
    assert result["meta"] == {"k": None}


def test_parse_returns_empty_when_no_pairs() -> None:
    """Return an empty dict when the message has no key=value pairs."""
    # Given a message with no key=value pairs
    parser = StructuredMessageParser()
    # When parsed
    result = parser.parse("just a plain message")
    # Then the result is empty
    assert result == {}


def test_clean_message_strips_extracted_pairs() -> None:
    """Strip extracted pairs, leaving only the human-readable prefix."""
    # Given a message with a prefix and key=value pairs
    parser = StructuredMessageParser()
    # When cleaned
    cleaned = parser.clean_message("HTTP Request: path=/v1/x method=POST")
    # Then only the human-readable prefix remains
    assert cleaned == "HTTP Request"


def test_clean_message_returns_original_when_fully_stripped() -> None:
    """Return the original message when stripping all pairs would leave nothing."""
    # Given a message that is entirely key=value pairs
    parser = StructuredMessageParser()
    message = "path=/v1/x method=POST"
    # When cleaned
    cleaned = parser.clean_message(message)
    # Then the original message is returned rather than an empty string
    assert cleaned == message


def test_parse_keeps_non_finite_floats_as_strings() -> None:
    """Verify nan/inf tokens stay strings so the JSON output remains valid."""
    # Given a message with IEEE special-value tokens that float() would accept
    parser = StructuredMessageParser()
    message = "a=nan b=inf c=-inf d=Infinity"
    # When parsed
    result = parser.parse(message)
    # Then they are left as their original strings (json.dumps emits invalid NaN/Infinity for floats)
    assert result == {"a": "nan", "b": "inf", "c": "-inf", "d": "Infinity"}


@pytest.mark.parametrize(
    ("level", "expected_color"),
    [
        (logging.DEBUG, "\x1b[40;1m"),
        (logging.INFO, "\x1b[34;1m"),
        (logging.WARNING, "\x1b[33;1m"),
        (logging.ERROR, "\x1b[31m"),
        (logging.CRITICAL, "\x1b[41m"),
        (25, "\x1b[40;1m"),
    ],
    ids=["debug", "info", "warning", "error", "critical", "unmapped_falls_back_to_debug"],
)
def test_color_formatter_wraps_message_in_level_color(
    level: int,
    expected_color: str,
    make_log_record: Callable[..., logging.LogRecord],
) -> None:
    """Render the message with the level's ANSI color, unmapped levels falling back to DEBUG."""
    # Given a record at the given level (25 is a custom level absent from the color map)
    formatter = ColorFormatter()
    record = make_log_record("hello world", level=level)
    # When formatted
    output = formatter.format(record)
    # Then the expected color code and the message are present
    assert expected_color in output
    assert "hello world" in output


def test_color_formatter_strips_binary_payload(
    make_log_record: Callable[..., logging.LogRecord],
) -> None:
    """Replace binary payload bytes with the omission marker before coloring."""
    # Given a record whose message embeds a binary response body
    formatter = ColorFormatter()
    record = make_log_record("Content-Type: image/png\r\n\r\n\x89PNG\r\nrawbytes")
    # When formatted
    output = formatter.format(record)
    # Then the omission marker is present and the raw bytes are gone
    assert "[binary content omitted]" in output
    assert "rawbytes" not in output


def test_color_formatter_restores_record_after_format(
    make_log_record: Callable[..., logging.LogRecord],
) -> None:
    """Leave the record's msg unmutated after formatting sanitizes it for output."""
    # Given a record with binary content in its message
    formatter = ColorFormatter()
    original = "Content-Type: image/png\r\n\r\nrawbytes"
    record = make_log_record(original)
    # When formatted
    formatter.format(record)
    # Then the record's msg is restored to its original value
    assert record.msg == original


def test_color_formatter_colors_exception_traceback(
    make_log_record: Callable[..., logging.LogRecord],
) -> None:
    """Wrap traceback text in the red escape sequence and restore exc_text afterwards."""
    # Given an ERROR record carrying exception info
    formatter = ColorFormatter()
    exc_info = _capture_exc_info()
    record = make_log_record("request failed", level=logging.ERROR, exc_info=exc_info)
    # When formatted
    output = formatter.format(record)
    # Then the traceback is wrapped in red and the record's exc_text is restored to its original None
    assert "\x1b[31mTraceback" in output
    assert "ValueError: boom" in output
    assert record.exc_text is None


def test_color_formatter_appends_extra_fields(
    make_log_record: Callable[..., logging.LogRecord],
) -> None:
    """Append non-standard record attributes to the formatted output."""
    # Given a record carrying an extra attribute
    formatter = ColorFormatter()
    record = make_log_record("with extras", user_id=42)
    # When formatted
    output = formatter.format(record)
    # Then the extra field appears in the appended dict
    assert "'user_id': 42" in output


def test_json_formatter_promotes_structured_fields(
    make_log_record: Callable[..., logging.LogRecord],
) -> None:
    """Promote key=value pairs to top-level JSON fields and clean the message text."""
    # Given a record with a prefix and structured key=value pairs
    formatter = LitestarJsonFormatter()
    record = make_log_record("HTTP Request: path=/v1/x method=POST status_code=200")
    # When formatted and parsed as JSON
    result = json.loads(formatter.format(record))
    # Then the pairs become typed fields and the message keeps only the human-readable prefix
    assert result["path"] == "/v1/x"
    assert result["method"] == "POST"
    assert result["status_code"] == 200
    assert result["message"] == "HTTP Request"


def test_json_formatter_keeps_plain_message_unchanged(
    make_log_record: Callable[..., logging.LogRecord],
) -> None:
    """Store the raw message when it has no key=value pairs to extract."""
    # Given a record with a plain message
    formatter = LitestarJsonFormatter()
    record = make_log_record("just a plain message")
    # When formatted and parsed as JSON
    result = json.loads(formatter.format(record))
    # Then the message is stored unchanged and no spurious fields are added
    assert result["message"] == "just a plain message"


def test_json_formatter_strips_binary_payload(
    make_log_record: Callable[..., logging.LogRecord],
) -> None:
    """Replace binary payload bytes with the omission marker in the JSON message field."""
    # Given a record whose message embeds a binary response body
    formatter = LitestarJsonFormatter()
    record = make_log_record("Content-Type: image/png\r\n\r\nrawbytes")
    # When formatted and parsed as JSON
    result = json.loads(formatter.format(record))
    # Then the omission marker replaces the raw bytes
    assert "[binary content omitted]" in result["message"]
    assert "rawbytes" not in result["message"]
