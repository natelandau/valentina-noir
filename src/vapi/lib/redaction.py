"""Credential redaction for request bodies written to logs and the audit table."""

from typing import Any

from vapi.constants import SENSITIVE_BODY_KEYS


def sanitize_json(value: Any, *, placeholder: str) -> Any:
    """Return a copy of a parsed JSON value that is safe to persist or log.

    Replace the value of every key in ``SENSITIVE_BODY_KEYS`` with ``placeholder``, at any
    depth and in any letter case, and replace NUL characters with U+FFFD because PostgreSQL
    text and jsonb columns reject them. Recurses once per nesting level, so a value nested
    deeper than the interpreter's recursion limit raises ``RecursionError``.

    Args:
        value: A value decoded from JSON.
        placeholder: Text that stands in for each redacted value.

    Returns:
        The sanitized copy.
    """
    if isinstance(value, str):
        return value.replace("\x00", "\ufffd")
    if isinstance(value, dict):
        return {
            sanitize_json(k, placeholder=placeholder): placeholder
            if k.lower() in SENSITIVE_BODY_KEYS
            else sanitize_json(v, placeholder=placeholder)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [sanitize_json(item, placeholder=placeholder) for item in value]
    return value
