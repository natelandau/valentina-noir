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
    ("reference", "birth_year", "date_of_birth", "expected"),
    [
        (date(1986, 6, 1), 1960, None, 26),
        (date(2003, 1, 1), 1960, None, 43),
        (date(1986, 6, 1), 1960, date(1960, 3, 15), 26),
        (date(1986, 3, 14), 1960, date(1960, 3, 15), 25),
        (date(1986, 3, 15), 1960, date(1960, 3, 15), 26),
        (date(1986, 6, 1), None, date(1960, 3, 15), 26),
        (date(1986, 6, 1), -1250, None, 3236),
        (date(1986, 6, 1), 1986, None, 0),
        (date(1986, 6, 1), 1990, None, None),
        (date(1986, 6, 1), None, None, None),
    ],
)
def test_age_on(
    reference: date, birth_year: int | None, date_of_birth: date | None, expected: int | None
) -> None:
    """Verify age is measured on the reference date from the birth year or full birth date."""
    # Given a reference date and what is known of the birth
    # When the age is measured
    age = age_on(reference, birth_year=birth_year, date_of_birth=date_of_birth)

    # Then it counts whole years, honoring the birthday when known
    assert age == expected
