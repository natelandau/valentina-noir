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


def age_on(reference: date, *, date_of_birth: date) -> int | None:
    """Return the whole years from a date of birth to a reference date.

    Args:
        reference: The date to measure the age on.
        date_of_birth: The date of birth.

    Returns:
        int | None: The age in whole years, counting whether the birthday has passed, or
            None when the reference date falls before the birth.
    """
    age = reference.year - date_of_birth.year
    if (reference.month, reference.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    return age if age >= 0 else None
