"""Unit tests for the gate-cache helpers in duties.py."""

import subprocess

import duties
import pytest
from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        ((), ["gate-cache", "--name", "t", "--", "pytest"]),
        (
            ("src/", "uv.lock"),
            ["gate-cache", "--name", "t", "--path", "src/", "--path", "uv.lock", "--", "pytest"],
        ),
    ],
)
def test_gated(paths: tuple[str, ...], expected: list[str]) -> None:
    """Verify each path becomes its own --path option before the command."""
    # Then
    assert duties.gated("t", ["pytest"], paths) == expected


def test_gate_passed_passes_paths(mocker: MockerFixture) -> None:
    """Verify the status check scopes to the same paths as the run."""
    # Given
    mocker.patch.object(duties, "GATE_CACHE_ON", new=True)
    run = mocker.patch.object(
        duties.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
    )

    # When
    passed = duties.gate_passed("t", ("src/",))

    # Then
    assert passed is True
    assert run.call_args.args[0] == ["gate-cache", "status", "--name", "t", "--path", "src/"]


def test_test_gate_paths_exist() -> None:
    """Verify every watched path exists, since gate-cache runs uncached on a path that matches nothing."""
    # Then
    for path in duties.TEST_GATE_PATHS:
        assert (duties.PROJECT_ROOT / path).exists(), path


def test_test_gate_paths_include_suite_inputs() -> None:
    """Verify the gate watches the task file and interpreter pin, which the suite also depends on."""
    # Then
    assert {"duties.py", ".python-version", "compose.yml"} <= set(duties.TEST_GATE_PATHS)
