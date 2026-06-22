"""Test the strings module."""

from __future__ import annotations

import re

import pytest

from vapi.utils import strings

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("value", "separator", "allow_unicode", "expected"),
    [
        ("Hello World", None, False, "hello-world"),
        ("Hello World", None, True, "hello-world"),
        ("Hello World", "_", False, "hello_world"),
        ("Café World", None, True, "café-world"),
        ("Café World", None, False, "cafe-world"),
    ],
)
def test_slugify(*, value: str, separator: str | None, allow_unicode: bool, expected: str) -> None:
    """Verify that the slugify function is working correctly."""
    assert (
        strings.slugify(value=value, separator=separator, allow_unicode=allow_unicode) == expected
    )


@pytest.mark.parametrize(
    ("num", "as_shortcode", "expected"),
    [
        (0, False, "0️⃣"),
        (0, True, ":zero:"),
        (10, False, "🔟"),
        (10, True, ":keycap_ten:"),
        (11, False, "11"),
        (11, True, "`11`"),
    ],
)
def test_convert_int_to_emoji(*, num: int, as_shortcode: bool, expected: str) -> None:
    """Verify that the convert_int_to_emoji function is working correctly."""
    assert strings.convert_int_to_emoji(num=num, as_shortcode=as_shortcode) == expected


def test_random_string(debug) -> None:
    """Test random_string()."""
    returned = strings.random_string(10)

    assert isinstance(returned, str)
    assert len(returned) == 10
    assert re.match(r"[a-zA-Z]{10}", returned)
