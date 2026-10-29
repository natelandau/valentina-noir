"""Unit tests for Compose invocation helpers."""

import os
from pathlib import Path

import pytest
from scripts.devenv.compose import compose_cmd, compose_env, ensure_generated_env
from scripts.devenv.ports import StackPorts


def test_compose_env_carries_ports_and_ids() -> None:
    """Verify the Compose environment adds ports, host IDs, and the debugpy flag."""
    # Given
    ports = StackPorts.for_slot(2)

    # When
    env = compose_env(ports=ports, debug=True)
    env_no_debug = compose_env(ports=ports, debug=False)

    # Then
    assert env["VAPI_DEV_API_PORT"] == "24120"
    assert env["VAPI_DEV_DEBUGPY_PORT"] == "24127"
    assert env["VAPI_DEV_UID"] == str(os.getuid())
    assert env["VAPI_DEV_GID"] == str(os.getgid())
    assert env["VAPI_DEV_DEBUGPY"] == "1"
    assert env_no_debug["VAPI_DEV_DEBUGPY"] == "0"
    assert env["PATH"] == os.environ["PATH"]


def test_compose_cmd_names_project_and_directory(tmp_path: Path) -> None:
    """Verify the command pins the project directory and project name."""
    # Given
    checkout = tmp_path / "checkout"

    # When
    cmd = compose_cmd("up", "-d", checkout=checkout, project="vapi-main")

    # Then
    assert cmd == [
        "docker",
        "compose",
        "--project-directory",
        str(checkout),
        "-p",
        "vapi-main",
        "up",
        "-d",
    ]


def test_ensure_generated_env_writes_once(tmp_path: Path) -> None:
    """Verify the generated env file holds both keys and is never overwritten."""
    # Given
    checkout = tmp_path

    # When
    path = ensure_generated_env(checkout)
    first = path.read_bytes()
    second_path = ensure_generated_env(checkout)

    # Then
    assert path == checkout / ".dev" / "generated.env"
    assert second_path == path
    assert path.read_bytes() == first
    lines = dict(line.split("=", 1) for line in first.decode().splitlines() if line)
    assert len(lines["VAPI_AUTHENTICATION_ENCRYPTION_KEY"]) == 64
    assert len(lines["VAPI_RATE_LIMIT__ENCRYPTION_KEY"]) == 64
    assert lines["VAPI_AUTHENTICATION_ENCRYPTION_KEY"] != lines["VAPI_RATE_LIMIT__ENCRYPTION_KEY"]


def test_ensure_generated_env_is_private(tmp_path: Path) -> None:
    """Verify the generated env file is readable and writable by its owner only."""
    # Given
    checkout = tmp_path

    # When
    path = ensure_generated_env(checkout)

    # Then
    assert path.stat().st_mode & 0o777 == 0o600


def test_compose_env_overrides_host_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the stack's variables win over the same names in the host environment."""
    # Given
    monkeypatch.setenv("VAPI_DEV_API_PORT", "9999")
    monkeypatch.setenv("VAPI_DEV_DEBUGPY", "1")

    # When
    env = compose_env(ports=StackPorts.for_slot(1), debug=False)

    # Then
    assert env["VAPI_DEV_API_PORT"] == "24110"
    assert env["VAPI_DEV_DEBUGPY"] == "0"
