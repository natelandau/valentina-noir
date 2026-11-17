"""Tests for credential redaction."""

import pytest

from vapi.constants import SENSITIVE_BODY_KEYS
from vapi.lib.redaction import sanitize_json


@pytest.mark.parametrize("key", sorted(SENSITIVE_BODY_KEYS))
def test_redacts_each_sensitive_key(key: str) -> None:
    """Verify every shared sensitive key is redacted and other keys are kept."""
    # Given a body with one credential beside an ordinary field
    body = {"provider": "google", key: "live-credential"}

    # When sanitizing it
    result = sanitize_json(body, placeholder="X")

    # Then only the credential is replaced
    assert result == {"provider": "google", key: "X"}


def test_matches_keys_case_insensitively() -> None:
    """Verify a sensitive key in another letter case is still redacted."""
    # Given credential keys in mixed case

    # When sanitizing
    result = sanitize_json({"Access_Token": "a", "PASSWORD": "b"}, placeholder="X")

    # Then both are redacted
    assert result == {"Access_Token": "X", "PASSWORD": "X"}


def test_redacts_inside_nested_objects_and_arrays() -> None:
    """Verify credentials are redacted at any depth, inside objects and arrays alike."""
    # Given credentials nested in objects and arrays
    body = [
        {"name": "a", "token": "t1"},
        {"name": "b", "items": [{"api_key": "k1"}, "plain"], "auth": {"meta": {"secret": "s"}}},
    ]

    # When sanitizing
    result = sanitize_json(body, placeholder="X")

    # Then every credential is replaced and other values are kept
    assert result == [
        {"name": "a", "token": "X"},
        {"name": "b", "items": [{"api_key": "X"}, "plain"], "auth": {"meta": {"secret": "X"}}},
    ]


def test_redacts_whole_value_of_sensitive_key() -> None:
    """Verify a sensitive key holding an object is replaced as a whole."""
    # Given a sensitive key whose value is itself an object

    # When sanitizing
    result = sanitize_json({"secret": {"inner": "value"}}, placeholder="X")

    # Then the whole value is redacted
    assert result == {"secret": "X"}


def test_replaces_nul_in_keys_and_values() -> None:
    """Verify NUL characters are replaced so PostgreSQL accepts the value."""
    # Given NULs in a key and a value

    # When sanitizing
    result = sanitize_json({"a\x00": ["b\x00"]}, placeholder="X")

    # Then each NUL becomes U+FFFD
    assert result == {"a\ufffd": ["b\ufffd"]}


def test_leaves_scalars_unchanged() -> None:
    """Verify non-container, non-string values pass through."""
    # Given scalar JSON values

    # When sanitizing each
    results = [sanitize_json(value, placeholder="X") for value in (None, 1, 2.5, True)]

    # Then they are unchanged
    assert results == [None, 1, 2.5, True]
