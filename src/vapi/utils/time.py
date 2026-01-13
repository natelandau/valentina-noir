"""Time utilities."""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ("time_now",)


def time_now() -> datetime:
    """Return the current time in UTC.

    Returns:
        datetime: The current UTC time with microseconds set to 0.
    """
    return datetime.now(UTC).replace(microsecond=0)
