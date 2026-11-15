"""Time utilities."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

__all__ = ("age_on", "format_uptime", "time_now")


def time_now() -> datetime:
    """Return the current time in UTC.

    Returns:
        datetime: The current UTC time with microseconds set to 0.
    """
    return datetime.now(UTC).replace(microsecond=0)


def format_uptime(delta: timedelta) -> str:
    """Format a timedelta as a human-readable duration string.

    Produce a compact representation like ``"2d 14h 32m 5s"`` suitable for
    health-check responses.

    Args:
        delta: The duration to format.

    Returns:
        str: Formatted string in the form ``"Xd Xh Xm Xs"``.
    """
    total_seconds = int(delta.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


def age_on(
    reference: date, *, birth_year: int | None, date_of_birth: date | None = None
) -> int | None:
    """Return a character's age on a reference date, typically the campaign's in-game date.

    A full date of birth gives the exact age, counting whether the birthday has passed.
    A birth year alone gives the difference in years.

    Args:
        reference: The date to measure the age on.
        birth_year: The year the character was born. Negative years are BCE.
        date_of_birth: The full date of birth, when known.

    Returns:
        int | None: The age in whole years, or None when no birth year is known or the
            reference date falls before the birth.
    """
    if date_of_birth is not None:
        age = reference.year - date_of_birth.year
        if (reference.month, reference.day) < (date_of_birth.month, date_of_birth.day):
            age -= 1
    elif birth_year is not None:
        age = reference.year - birth_year
    else:
        return None
    return age if age >= 0 else None
