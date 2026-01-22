"""Test the validation module."""

from __future__ import annotations

import pytest

from vapi.lib import validation

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", None),
        ("   ", None),
        ("\t", None),
        ("\n", None),
        ("  \t\n  ", None),
        ("hello", "hello"),
        ("hello world", "hello world"),
        ("  hello  ", "  hello  "),
        ("123", "123"),
        ("test\nwith\nnewlines", "test\nwith\nnewlines"),
    ],
)
def test_empty_string_to_none(*, value: str, expected: str | None) -> None:
    """Verify converting empty or whitespace-only strings to None."""
    assert validation.empty_string_to_none(value=value) == expected
