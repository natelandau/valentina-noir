"""Math utilities."""

from __future__ import annotations

import math

from numpy.random import default_rng

_rng = default_rng()
__all__ = ("random_num", "roll_percentile", "round_up")


def random_num(ceiling: int = 100) -> int:
    """Generate a random integer within a specified range.

    Generate and return a random integer between 1 and the given ceiling (inclusive).

    Args:
        ceiling (int, optional): The upper limit for the random number. Defaults to 100.

    Returns:
        int: A random integer between 1 and the ceiling.

    Raises:
        ValueError: If ceiling is less than 1.
    """
    return int(_rng.integers(1, ceiling + 1))


def round_up(value: float, decimals: int = 2) -> float:
    """Round a number upward to a given number of decimal places.

    Unlike the built-in :func:`round`, this function always rounds
    toward positive infinity at the specified decimal precision.

    Args:
        value (float): The number to round.
        decimals (int, optional): Number of decimal places to keep (the default is 2).

    Returns:
        float: The rounded number.
    """
    factor = 10**decimals
    return math.ceil(value * factor) / factor


def roll_percentile() -> int:
    """Roll a percentile."""
    return random_num(100)
