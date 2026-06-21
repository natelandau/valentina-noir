"""Test the time module."""

from __future__ import annotations

from datetime import timedelta

import pytest

from vapi.utils.time import format_uptime


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(seconds=0), "0d 0h 0m 0s"),
        (timedelta(seconds=45), "0d 0h 0m 45s"),
        (timedelta(seconds=125), "0d 0h 2m 5s"),
        (timedelta(seconds=3661), "0d 1h 1m 1s"),
        (timedelta(seconds=90061), "1d 1h 1m 1s"),
        (timedelta(days=5, hours=3, minutes=22, seconds=17), "5d 3h 22m 17s"),
    ],
)
def test_format_uptime(delta: timedelta, expected: str) -> None:
    """Verify duration is formatted as a human-readable string."""
    # Given a timedelta

    # When formatting it
    result = format_uptime(delta)

    # Then the output matches the expected string
    assert result == expected
