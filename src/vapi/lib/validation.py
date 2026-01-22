"""Validation."""

from __future__ import annotations


def empty_string_to_none(value: str) -> str | None:
    """Convert an empty string to None."""
    if not value:
        return None

    if value.strip() == "":
        return None
    return value
