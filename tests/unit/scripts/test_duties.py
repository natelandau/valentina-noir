"""Unit tests for the gate-cache helpers in duties.py."""

from pathlib import Path

import duties
import pytest


@pytest.mark.parametrize(
    ("paths", "junit", "expected"),
    [
        ((), None, ["gate-cache", "--name", "t", "--", "pytest"]),
        (
            ("src/", "uv.lock"),
            None,
            ["gate-cache", "--name", "t", "--path", "src/", "--path", "uv.lock", "--", "pytest"],
        ),
        ((), Path("r.xml"), ["gate-cache", "--name", "t", "--junit", "r.xml", "--", "pytest"]),
    ],
)
def test_gated(paths: tuple[str, ...], junit: Path | None, expected: list[str]) -> None:
    """Verify each path and the JUnit report become gate-cache options before the command."""
    # Then
    assert duties.gated("t", ["pytest"], paths, junit=junit) == expected


def test_test_gate_paths_exist() -> None:
    """Verify every watched path exists, since gate-cache runs uncached on a path that matches nothing."""
    # Then
    for path in duties.TEST_GATE_PATHS:
        assert (duties.PROJECT_ROOT / path).exists(), path


def test_test_gate_paths_include_suite_inputs() -> None:
    """Verify the gate watches the task file and interpreter pin, which the suite also depends on."""
    # Then
    assert {"duties.py", ".python-version", "compose.yml"} <= set(duties.TEST_GATE_PATHS)
