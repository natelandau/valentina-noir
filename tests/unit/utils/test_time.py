"""Test the time module."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from vapi.utils.time import age_on, format_uptime


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


@pytest.mark.parametrize(
    ("reference", "date_of_birth", "expected"),
    [
        (date(1986, 6, 1), date(1960, 3, 15), 26),
        (date(1986, 3, 14), date(1960, 3, 15), 25),
        (date(1986, 3, 15), date(1960, 3, 15), 26),
        (date(2003, 1, 1), date(1960, 3, 15), 42),
        (date(1960, 3, 15), date(1960, 3, 15), 0),
        (date(1960, 3, 14), date(1960, 3, 15), None),
    ],
)
def test_age_on(reference: date, date_of_birth: date, expected: int | None) -> None:
    """Verify age counts whole years on the reference date, honoring the birthday."""
    # Given a reference date and a date of birth
    # When the age is measured
    age = age_on(reference, date_of_birth=date_of_birth)

    # Then it counts whole years, or None before the birth
    assert age == expected
