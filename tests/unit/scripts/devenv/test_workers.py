"""Unit tests for the number of pytest-xdist workers on a developer machine."""

import pytest
from scripts.devenv.workers import auto_num_workers, ci_is_on


@pytest.mark.parametrize(
    ("cpu_count", "expected"),
    [(None, 2), (1, 2), (2, 2), (4, 3), (8, 6), (14, 11), (16, 12), (32, 24)],
)
def test_auto_num_workers_leaves_a_quarter_free(cpu_count: int | None, expected: int) -> None:
    """Verify a developer machine keeps a quarter of its cores, at least one, with two workers minimum."""
    # Then
    assert auto_num_workers({}, cpu_count) == expected


@pytest.mark.parametrize("ci", ["true", "1", "TRUE"])
def test_auto_num_workers_defers_to_xdist_in_ci(ci: str) -> None:
    """Verify CI keeps xdist's own count, which uses every core."""
    # Then
    assert auto_num_workers({"CI": ci}, 4) is None


@pytest.mark.parametrize("ci", ["", "0", "false", "False"])
def test_auto_num_workers_caps_when_ci_is_off(ci: str) -> None:
    """Verify a CI variable set to an off value still caps the workers."""
    # Then
    assert auto_num_workers({"CI": ci}, 8) == 6


def test_auto_num_workers_defers_to_an_exported_count() -> None:
    """Verify an exported PYTEST_XDIST_AUTO_NUM_WORKERS wins, handled by xdist itself."""
    # Then
    assert auto_num_workers({"PYTEST_XDIST_AUTO_NUM_WORKERS": "6"}, 14) is None


def test_auto_num_workers_caps_when_the_exported_count_is_not_a_number() -> None:
    """Verify a value xdist ignores does not bypass the cap."""
    # Then
    assert auto_num_workers({"PYTEST_XDIST_AUTO_NUM_WORKERS": "many"}, 8) == 6


@pytest.mark.parametrize(
    ("ci", "expected"), [("", False), ("0", False), ("FALSE", False), ("1", True)]
)
def test_ci_is_on(ci: str, expected: bool) -> None:
    """Verify CI follows gate-cache's on and off values."""
    # Then
    assert ci_is_on({"CI": ci}) is expected
