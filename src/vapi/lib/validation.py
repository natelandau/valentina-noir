"""Validation."""

from __future__ import annotations

import re


def validate_string(value: str) -> str:
    """Validate a string."""
    value = value.strip()
    without_special_chars = re.sub(r"[^a-zA-Z0-9]", "", value)

    if len(without_special_chars) < 2:  # noqa: PLR2004
        msg = "Must contain at least 2 alphanumeric characters"
        raise ValueError(msg)

    return value


def empty_string_to_none(value: str) -> str | None:
    """Convert an empty string to None."""
    if not value:
        return None

    if value.strip() == "":
        return None
    return value
