"""Time utilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

__all__ = ("format_uptime", "time_now")


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
