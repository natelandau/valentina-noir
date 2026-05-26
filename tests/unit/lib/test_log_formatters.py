"""Tests for log formatters and the structured key=value message parser."""

from vapi.lib.log_formatters import StructuredMessageParser


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
