"""Test the math module."""

from __future__ import annotations

import pytest

from vapi.utils import math

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [
        (1.23456789, 2, 1.24),
        (1.20456789, 3, 1.205),
        (1.20056789, 1, 1.3),
        (1.20056789, 0, 2),
    ],
)
def test_round_up(value: float, decimals: int, expected: float) -> None:
    """Test the round_up function."""
    assert math.round_up(value, decimals) == expected


@pytest.mark.parametrize(
    ("ceiling"),
    [(1), (100), (50)],
)
@pytest.mark.repeat(20)
def test_random_num(*, ceiling: int) -> None:
    """Test the random_num function."""
    assert math.random_num(ceiling) in range(1, ceiling + 1)
