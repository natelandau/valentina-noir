"""Unit tests for dev stack orchestration. Every subprocess call is faked; no Docker runs."""

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from rich.console import Console
from scripts.devenv import stack as stack_module
from scripts.devenv.compose import StackError
from scripts.devenv.copy import MainNotInitializedError
from scripts.devenv.ports import StackPorts
from scripts.devenv.registry import Registry
from scripts.devenv.stack import (
    PortInUseError,
    Stack,
    envs,
    load_stack,
    populate,
    preflight_ports,
    reset,
    run_task,
    start_test_services,
    up,
)


class FakeRun:
    """Stand-in for `subprocess.run` that records commands and answers from a responder."""

    def __init__(self, respond: Callable[[list[str]], tuple[int, str]] | None = None) -> None:
        self.calls: list[list[str]] = []
        self._respond = respond or (lambda _cmd: (0, ""))

    def __call__(self, cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(cmd))
        code, stdout = self._respond(list(cmd))
        return subprocess.CompletedProcess(cmd, code, stdout=stdout, stderr="")

    def ran(self, *fragment: str) -> bool:
        """Return whether any recorded command contains the fragment as a contiguous run."""
        size = len(fragment)
        return any(
            call[index : index + size] == list(fragment)
            for call in self.calls
            for index in range(len(call) - size + 1)
        )


@pytest.fixture
def quiet_stack(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[dict[str, object]]:
    """Stub the network and Docker-facing helpers `up` calls, recording copies from main."""
    copies: list[dict[str, object]] = []
    monkeypatch.setenv("VAPI_DEV_REGISTRY", str(tmp_path / "registry.json"))
    monkeypatch.setattr(stack_module, "preflight_ports", lambda _ports, *, project: None)
    monkeypatch.setattr(stack_module, "ensure_bucket", lambda *, endpoint, bucket: None)
    monkeypatch.setattr(stack_module, "is_fresh", lambda *, checkout, project: True)
    monkeypatch.setattr(stack_module, "copy_from_main", lambda **kwargs: copies.append(kwargs))
    return copies


def test_preflight_ports_names_foreign_holder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a port held by another process fails with the port and the holder's name."""

    # Given lsof reports node listening on the API port and Docker lists no containers
    def respond(cmd: list[str]) -> tuple[int, str]:
        if cmd[0] == "lsof" and "-iTCP:24110" in cmd:
            return 0, "p123\ncnode\nf20\n"
        if cmd[0] == "lsof":
            return 1, ""
        return 0, ""

    monkeypatch.setattr(stack_module.subprocess, "run", FakeRun(respond))

    # When / Then
    with pytest.raises(PortInUseError) as error:
        preflight_ports(StackPorts.for_slot(1), project="vapi-feat-12345678")
    assert "24110" in str(error.value)
    assert "node" in str(error.value)


def test_preflight_ports_allows_own_containers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify ports published by the stack's own containers do not count as conflicts."""
    # Given Docker's proxy holds every port, and the project's containers publish them all
    ports = StackPorts.for_slot(1)
    published = (
        "127.0.0.1:24110->8000/tcp, 127.0.0.1:24117->5678/tcp\n"
        "127.0.0.1:24111->5432/tcp\n"
        "127.0.0.1:24112->6379/tcp\n"
        "127.0.0.1:24113-24114->9000-9001/tcp\n"
        "127.0.0.1:24115->5432/tcp\n"
        "127.0.0.1:24116->6379/tcp\n"
    )

    def respond(cmd: list[str]) -> tuple[int, str]:
        if cmd[0] == "lsof":
            return 0, "p999\nccom.docker.backend\nf20\n"
        if cmd[:2] == ["docker", "ps"]:
            return 0, published
        return 0, ""

    monkeypatch.setattr(stack_module.subprocess, "run", FakeRun(respond))

    # When
    preflight_ports(ports, project="vapi-feat-12345678")

    # Then no error was raised


def test_up_reports_main_ahead_on_migration_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    quiet_stack: list[dict[str, object]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify a failed migration after a copy from main explains how to rebuild fresh."""
    # Given a fresh worktree stack whose migration fails after the copy
    stack = Stack(checkout=tmp_path / "wt", branch="feat", main=tmp_path / "main", slot=1)
    fake = FakeRun(lambda cmd: (1, "") if cmd[-2:] == ["app", "migrate"] else (0, ""))
    monkeypatch.setattr(stack_module.subprocess, "run", fake)

    # When
    with pytest.raises(SystemExit) as error:
        up(stack)

    # Then
    output = " ".join(capsys.readouterr().out.split())
    assert error.value.code == 1
    assert len(quiet_stack) == 1
    assert "main's data is ahead" in output
    assert "uv run duty reset fresh=true" in output
    assert not fake.ran("up", "-d", "--wait", "api")


def test_reset_worktree_recopies_and_main_repopulates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, quiet_stack: list[dict[str, object]]
) -> None:
    """Verify reset drops volumes, then a worktree recopies from main and main repopulates."""
    # Given confirmation is granted and every command succeeds
    monkeypatch.setattr(stack_module.Confirm, "ask", lambda *_args, **_kwargs: True)
    worktree = Stack(checkout=tmp_path / "wt", branch="feat", main=tmp_path / "main", slot=1)
    main = Stack(checkout=tmp_path / "main", branch=None, main=tmp_path / "main", slot=0)
    worktree_run = FakeRun()
    main_run = FakeRun()

    # When
    monkeypatch.setattr(stack_module.subprocess, "run", worktree_run)
    reset(worktree)
    copies_after_worktree = len(quiet_stack)
    monkeypatch.setattr(stack_module.subprocess, "run", main_run)
    reset(main)

    # Then
    assert worktree_run.ran("down", "-v")
    assert copies_after_worktree == 1
    assert not worktree_run.ran("scripts.populate_dev_db")
    assert (tmp_path / "wt" / ".dev" / "origin").read_text().strip() == "copied-from-main"
    assert main_run.ran("down", "-v")
    assert main_run.ran("scripts.populate_dev_db", "--yes")
    assert len(quiet_stack) == 1
    assert (tmp_path / "main" / ".dev" / "origin").read_text().strip() == "populated"


def test_reset_worktree_fresh_populates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, quiet_stack: list[dict[str, object]]
) -> None:
    """Verify `reset fresh=true` in a worktree rebuilds from populate instead of copying."""
    # Given
    monkeypatch.setattr(stack_module.Confirm, "ask", lambda *_args, **_kwargs: True)
    worktree = Stack(checkout=tmp_path / "wt", branch="feat", main=tmp_path / "main", slot=1)
    fake = FakeRun()
    monkeypatch.setattr(stack_module.subprocess, "run", fake)

    # When
    reset(worktree, fresh=True)

    # Then
    assert quiet_stack == []
    assert fake.ran("scripts.populate_dev_db", "--yes")


def test_reset_aborts_without_confirmation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, quiet_stack: list[dict[str, object]]
) -> None:
    """Verify a declined prompt leaves the stack untouched."""
    # Given
    monkeypatch.setattr(stack_module.Confirm, "ask", lambda *_args, **_kwargs: False)
    worktree = Stack(checkout=tmp_path / "wt", branch="feat", main=tmp_path / "main", slot=1)
    fake = FakeRun()
    monkeypatch.setattr(stack_module.subprocess, "run", fake)

    # When
    reset(worktree)

    # Then
    assert fake.calls == []
    assert quiet_stack == []


def test_up_reuses_recorded_origin_and_registers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, quiet_stack: list[dict[str, object]]
) -> None:
    """Verify a later `up` keeps the recorded origin and registers the sheet's developers."""
    # Given an initialized worktree stack with a connection sheet
    monkeypatch.setattr(stack_module, "is_fresh", lambda *, checkout, project: False)
    checkout = tmp_path / "wt"
    (checkout / ".dev").mkdir(parents=True)
    (checkout / ".dev" / "origin").write_text("copied-from-main\n")
    (checkout / ".dev" / "connection.json").write_text('{"developers": [{"username": "alice"}]}')
    stack = Stack(checkout=checkout, branch="feat", main=tmp_path / "main", slot=1)
    fake = FakeRun()
    monkeypatch.setattr(stack_module.subprocess, "run", fake)

    # When
    up(stack, debug=True)

    # Then
    env = stack_module.Registry.load().entries()["feat"]
    assert quiet_stack == []
    assert fake.ran("--origin", "copied-from-main")
    assert fake.ran("up", "-d", "--wait", "api")
    assert env.developers == [{"username": "alice"}]
    assert env.api_url == "http://127.0.0.1:24110"
    assert env.keys_file == checkout / ".dev" / "api-keys.json"
    assert env.slot == 1


def test_up_removes_half_made_stack_when_copy_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, quiet_stack: list[dict[str, object]]
) -> None:
    """Verify a copy that fails partway removes the stack's volumes and says to rerun `up`."""

    # Given the bucket mirror fails after the database was restored
    def failing_copy(**_kwargs: object) -> None:
        raise ClientError({"Error": {"Code": "500", "Message": "boom"}}, "PutObject")

    monkeypatch.setattr(stack_module, "copy_from_main", failing_copy)
    stack = Stack(checkout=tmp_path / "wt", branch="feat", main=tmp_path / "main", slot=1)
    fake = FakeRun()
    monkeypatch.setattr(stack_module.subprocess, "run", fake)

    # When / Then
    with pytest.raises(StackError, match="half-made stack was removed") as error:
        up(stack)
    assert "uv run duty up" in str(error.value)
    assert fake.ran("down", "-v")
    assert not fake.ran("app", "migrate")
    assert not (tmp_path / "wt" / ".dev" / "origin").exists()


def test_up_keeps_untouched_stack_when_main_is_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, quiet_stack: list[dict[str, object]]
) -> None:
    """Verify an empty main stops `up` without removing the still-empty worktree stack."""

    # Given
    def refuse(**_kwargs: object) -> None:
        msg = "Main's stack has no data to copy. Run `uv run duty up` in main first."
        raise MainNotInitializedError(msg)

    monkeypatch.setattr(stack_module, "copy_from_main", refuse)
    stack = Stack(checkout=tmp_path / "wt", branch="feat", main=tmp_path / "main", slot=1)
    fake = FakeRun()
    monkeypatch.setattr(stack_module.subprocess, "run", fake)

    # When / Then
    with pytest.raises(MainNotInitializedError):
        up(stack)
    assert not fake.ran("down", "-v")


def test_run_task_turns_failures_into_exit_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify stack errors and missing tools print a message and exit 1."""
    # Given
    stack = Stack(checkout=tmp_path, branch="feat", main=tmp_path, slot=1)
    claimed: list[bool] = []
    monkeypatch.setattr(stack_module, "load_stack", lambda _cwd: claimed.append(False) or stack)
    monkeypatch.setattr(stack_module, "claim_stack", lambda _cwd: claimed.append(True) or stack)

    def stack_failure(_stack: Stack) -> None:
        msg = "postgres is not running"
        raise StackError(msg)

    def missing_tool(_stack: Stack) -> None:
        raise FileNotFoundError(2, "No such file or directory", "lsof")

    # When
    with pytest.raises(SystemExit) as stack_exit:
        run_task(stack_failure, cwd=tmp_path)
    with pytest.raises(SystemExit) as tool_exit:
        run_task(missing_tool, cwd=tmp_path, claim=True)

    # Then
    output = capsys.readouterr().out
    assert stack_exit.value.code == 1
    assert tool_exit.value.code == 1
    assert "postgres is not running" in output
    assert "`lsof` was not found" in output
    assert claimed == [False, True]


def test_load_stack_requires_started_checkout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify a checkout with no slot claim points the developer at `uv run duty up`."""
    # Given an empty registry
    monkeypatch.setenv("VAPI_DEV_REGISTRY", str(tmp_path / "registry.json"))
    monkeypatch.setattr(stack_module, "checkout_identity", lambda _cwd: (tmp_path, "feat"))
    monkeypatch.setattr(stack_module, "main_checkout", lambda _cwd: tmp_path)

    # When / Then
    with pytest.raises(StackError, match="uv run duty up"):
        load_stack(tmp_path)


def test_envs_lists_registered_stacks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify `envs` shows each entry's key, slot, URL, and running state."""
    # Given a registered worktree stack with two running containers
    monkeypatch.setenv("VAPI_DEV_REGISTRY", str(tmp_path / "registry.json"))
    monkeypatch.setattr(stack_module, "console", Console(width=400))
    stack = Stack(checkout=tmp_path, branch="feat", main=tmp_path, slot=2)
    with Registry.locked() as registry:
        registry.upsert(stack.environment([]))
    monkeypatch.setattr(stack_module.subprocess, "run", FakeRun(lambda _cmd: (0, "abc\ndef\n")))

    # When
    envs()

    # Then
    output = capsys.readouterr().out
    assert "feat" in output
    assert "http://127.0.0.1:24120" in output
    assert "running (2 containers)" in output
    assert str(tmp_path / ".dev" / "connection.md") in output


def test_start_test_services_points_pytest_at_the_slot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify the test servers start under the stack's project and their slot ports are returned."""
    # Given a worktree stack in slot 2
    stack = Stack(checkout=tmp_path / "wt", branch="feat", main=tmp_path / "main", slot=2)
    fake = FakeRun()
    monkeypatch.setattr(stack_module.subprocess, "run", fake)

    # When
    env = start_test_services(stack)

    # Then
    assert fake.ran("-p", stack.project, "--profile", "test", "up", "-d", "--wait")
    assert fake.ran("postgres-test", "redis-test")
    assert env == {
        "VAPI_TEST_SERVICES_HOST": "127.0.0.1",
        "VAPI_TEST_POSTGRES_PORT": "24125",
        "VAPI_TEST_REDIS_PORT": "24126",
    }


def test_populate_passes_options_and_marks_origin(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, quiet_stack: list[dict[str, object]]
) -> None:
    """Verify populate forwards script options and records the data as populated."""
    # Given a running worktree stack whose data was copied from main
    monkeypatch.setattr(stack_module.Confirm, "ask", lambda *_args, **_kwargs: True)
    stack = Stack(checkout=tmp_path / "wt", branch="feat", main=tmp_path / "main", slot=1)
    stack.dev_dir.mkdir(parents=True)
    (stack.dev_dir / "origin").write_text("copied-from-main\n")
    fake = FakeRun(lambda cmd: (0, "container-id") if "ps" in cmd else (0, ""))
    monkeypatch.setattr(stack_module.subprocess, "run", fake)

    # When
    populate(stack, "--companies", "3")

    # Then
    assert fake.ran("scripts.populate_dev_db", "--yes", "--companies", "3")
    assert (stack.dev_dir / "origin").read_text().strip() == "populated"


@pytest.mark.parametrize("step", ["copy", "populate"])
def test_up_removes_half_made_stack_when_interrupted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    quiet_stack: list[dict[str, object]],
    step: str,
) -> None:
    """Verify Ctrl-C while filling the database removes the volumes and still interrupts."""

    # Given filling the database is interrupted partway
    def interrupted_copy(**_kwargs: object) -> None:
        raise KeyboardInterrupt

    def respond(cmd: list[str]) -> tuple[int, str]:
        if "scripts.populate_dev_db" in cmd:
            raise KeyboardInterrupt
        return 0, ""

    monkeypatch.setattr(stack_module, "copy_from_main", interrupted_copy)
    branch = "feat" if step == "copy" else None
    stack = Stack(checkout=tmp_path / "wt", branch=branch, main=tmp_path / "main", slot=1)
    fake = FakeRun(respond)
    monkeypatch.setattr(stack_module.subprocess, "run", fake)

    # When / Then
    with pytest.raises(KeyboardInterrupt):
        up(stack)
    assert fake.ran("down", "-v")
    assert not fake.ran("app", "migrate")
    assert not (tmp_path / "wt" / ".dev" / "origin").exists()


@pytest.mark.parametrize(
    "content",
    ["{not json", '{"schema_version": 7}', '{"schema_version": 1, "environments": {"a": {}}}'],
)
def test_run_task_reports_unreadable_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    content: str,
) -> None:
    """Verify a bad registry file names the file and says how to recover, then exits 1."""
    # Given a corrupt registry file
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(content)
    monkeypatch.setenv("VAPI_DEV_REGISTRY", str(registry_file))
    monkeypatch.setattr(stack_module, "checkout_identity", lambda _cwd: (tmp_path, "feat"))
    monkeypatch.setattr(stack_module, "main_checkout", lambda _cwd: tmp_path)

    # When
    with pytest.raises(SystemExit) as exit_info:
        run_task(lambda _stack: None, cwd=tmp_path)

    # Then
    output = capsys.readouterr().out
    assert exit_info.value.code == 1
    assert str(registry_file) in output.replace("\n", "")
    assert "fix or delete it" in output


def test_run_task_does_not_blame_registry_for_corrupt_connection_sheet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify a corrupt `.dev/connection.json` surfaces as itself, not as a registry problem."""
    # Given a valid registry and a corrupt connection sheet
    monkeypatch.setenv("VAPI_DEV_REGISTRY", str(tmp_path / "registry.json"))
    stack = Stack(checkout=tmp_path / "wt", branch="feat", main=tmp_path / "main", slot=1)
    (stack.dev_dir).mkdir(parents=True)
    (stack.dev_dir / "connection.json").write_text("{not json")
    monkeypatch.setattr(stack_module, "load_stack", lambda _cwd: stack)

    # When / Then
    with pytest.raises(json.JSONDecodeError):
        run_task(stack_module._register, cwd=tmp_path)
    assert "fix or delete it" not in capsys.readouterr().out


def test_reset_keeps_debug_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify `reset debug=true` rebuilds the stack with the debugger, as `up debug=true` does."""
    # Given
    monkeypatch.setattr(stack_module.Confirm, "ask", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(stack_module.subprocess, "run", FakeRun())
    calls: list[dict[str, bool]] = []
    monkeypatch.setattr(stack_module, "up", lambda _stack, **kwargs: calls.append(kwargs))
    main = Stack(checkout=tmp_path / "main", branch=None, main=tmp_path / "main", slot=0)

    # When
    reset(main, debug=True)

    # Then
    assert calls == [{"debug": True, "fresh": False}]
