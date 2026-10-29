"""Unit tests for worktree commands. Git runs for real in a temp repo; Docker and uv are faked."""

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from scripts.devenv import worktrees
from scripts.devenv.compose import StackError
from scripts.devenv.ports import StackPorts, project_name
from scripts.devenv.registry import MAIN_KEY, Environment, Registry

REAL_RUN = subprocess.run


class Recorder:
    """Records Docker and uv commands, runs git for real, and answers Docker from a responder."""

    def __init__(self, respond: Callable[[list[str]], int] | None = None) -> None:
        self.calls: list[list[str]] = []
        self._respond = respond or (lambda _cmd: 0)

    def __call__(self, cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if cmd[0] == "git":
            return REAL_RUN(cmd, **kwargs)
        self.calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, self._respond(list(cmd)), stdout="", stderr="")

    def ran(self, *fragment: str) -> bool:
        """Return whether any recorded command contains the fragment as a contiguous run."""
        size = len(fragment)
        return any(
            call[index : index + size] == list(fragment)
            for call in self.calls
            for index in range(len(call) - size + 1)
        )


def _git(cwd: Path, *args: str) -> None:
    REAL_RUN(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def main_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real git repo with one commit and an ignored CLAUDE.local.md, and a temp registry."""
    monkeypatch.setenv("VAPI_DEV_REGISTRY", str(tmp_path / "registry.json"))
    main = (tmp_path / "main").resolve()
    main.mkdir()
    _git(main, "init", "-b", "main")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / ".gitignore").write_text("CLAUDE.local.md\n.worktrees/\n")
    (main / "CLAUDE.local.md").write_text("local notes\n")
    _git(main, "add", ".gitignore")
    _git(main, "commit", "-m", "init")
    return main


def _register(*, key: str, slot: int, checkout: Path, project: str | None = None) -> None:
    branch_arg = None if key == MAIN_KEY else key
    with Registry.locked() as registry:
        registry.assign_slot(key=key, checkout=checkout)
        registry.upsert(
            Environment(
                key=key,
                checkout=checkout,
                branch=key,
                slot=slot,
                project=project or project_name(branch=branch_arg),
                ports=StackPorts.for_slot(slot),
                api_url="",
                api_url_from_containers="",
                healthz_url="",
                connection_sheet=checkout / ".dev" / "connection.md",
                keys_file=checkout / ".dev" / "api-keys.json",
            )
        )


def test_create_assigns_slot_and_registers(
    main_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify create adds the worktree, copies local files, claims a slot, and syncs deps."""
    # Given a main checkout
    recorder = Recorder()
    monkeypatch.setattr(worktrees.subprocess, "run", recorder)

    # When
    path = worktrees.create(main=main_repo, branch="feat-x")

    # Then the worktree exists below .worktrees with the local file copied
    assert path == main_repo / ".worktrees" / "feat-x"
    assert (path / "CLAUDE.local.md").read_text() == "local notes\n"
    # And a slot is claimed and registered, with dependencies synced in the worktree
    registry = Registry.load()
    assert registry.claimed_slot("feat-x") == 1
    assert registry.entries()["feat-x"].checkout == path
    assert recorder.ran("uv", "sync", "--all-groups")


def test_teardown_keeps_everything_when_tree_is_dirty(
    main_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify uncommitted files stop teardown before any Docker call, deleting nothing."""
    # Given a registered worktree with an uncommitted change
    recorder = Recorder()
    monkeypatch.setattr(worktrees.subprocess, "run", recorder)
    path = worktrees.create(main=main_repo, branch="feat-x")
    (path / "dirty.txt").write_text("x")
    recorder.calls.clear()

    # When
    with pytest.raises(StackError, match="uncommitted or untracked"):
        worktrees.teardown(main=main_repo, target=path)

    # Then
    assert not recorder.calls
    assert path.exists()
    assert Registry.load().claimed_slot("feat-x") == 1


def test_teardown_removes_volumes_worktree_and_entry(
    main_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify teardown downs the project with volumes, then removes the directory and entry."""
    # Given a registered worktree
    recorder = Recorder()
    monkeypatch.setattr(worktrees.subprocess, "run", recorder)
    path = worktrees.create(main=main_repo, branch="feat-x")

    # When
    worktrees.teardown(main=main_repo, target=path)

    # Then
    assert recorder.ran("--profile", "test", "down", "-v")
    assert recorder.ran("-p", project_name(branch="feat-x"))
    assert not path.exists()
    assert Registry.load().claimed_slot("feat-x") is None


def test_teardown_stops_before_removal_when_compose_fails(
    main_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a failed compose down (Docker off) keeps the worktree and entry."""
    # Given a registered worktree and Docker failing
    monkeypatch.setattr(worktrees.subprocess, "run", Recorder())
    path = worktrees.create(main=main_repo, branch="feat-x")
    monkeypatch.setattr(worktrees.subprocess, "run", Recorder(lambda _cmd: 1))

    # When
    with pytest.raises(StackError, match="Docker"):
        worktrees.teardown(main=main_repo, target=path)

    # Then
    assert path.exists()
    assert Registry.load().claimed_slot("feat-x") == 1


def test_teardown_refuses_main_checkout(main_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the main checkout cannot be torn down."""
    # Given
    recorder = Recorder()
    monkeypatch.setattr(worktrees.subprocess, "run", recorder)

    # When / Then
    with pytest.raises(StackError, match="main checkout"):
        worktrees.teardown(main=main_repo, target=main_repo)
    assert not recorder.calls


def test_prune_removes_only_missing_checkouts(
    main_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify prune drops entries whose checkout is gone and never touches main or live ones."""
    # Given main, a live worktree entry, and a missing one
    live = tmp_path / "live"
    live.mkdir()
    _register(key=MAIN_KEY, slot=0, checkout=tmp_path / "gone-main-path")
    _register(key="live", slot=1, checkout=live)
    _register(key="gone", slot=2, checkout=tmp_path / "gone")
    recorder = Recorder()
    monkeypatch.setattr(worktrees.subprocess, "run", recorder)

    # When
    pruned = worktrees.prune(main=main_repo)

    # Then
    assert pruned == ["gone"]
    assert recorder.ran("-p", project_name(branch="gone"), "--profile", "test", "down", "-v")
    assert not recorder.ran("-p", project_name(branch="live"))
    assert not recorder.ran("-p", project_name(branch=None))
    assert set(Registry.load().entries()) == {MAIN_KEY, "live"}


def test_teardown_rejects_detached_worktree_without_entry(
    main_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a detached-HEAD worktree with no entry never resolves to main's stack."""
    # Given a worktree detached from any branch and absent from the registry
    recorder = Recorder()
    monkeypatch.setattr(worktrees.subprocess, "run", recorder)
    path = main_repo / ".worktrees" / "detached"
    _git(main_repo, "worktree", "add", "--detach", str(path))
    _register(key=MAIN_KEY, slot=0, checkout=main_repo)

    # When
    with pytest.raises(StackError, match="not a worktree"):
        worktrees.teardown(main=main_repo, target=path)

    # Then no Docker command ran and main's entry is intact
    assert not recorder.calls
    assert path.exists()
    assert Registry.load().claimed_slot(MAIN_KEY) == 0


def test_teardown_rejects_path_outside_repository(
    main_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify a directory git does not list as a worktree is refused before Docker runs."""
    # Given
    recorder = Recorder()
    monkeypatch.setattr(worktrees.subprocess, "run", recorder)
    stray = tmp_path / "stray"
    stray.mkdir()

    # When / Then
    with pytest.raises(StackError, match="not a worktree"):
        worktrees.teardown(main=main_repo, target=stray)
    assert not recorder.calls


def test_create_releases_slot_when_git_fails(
    main_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a failed `git worktree add` leaves no slot claim behind."""
    # Given a branch name git rejects
    monkeypatch.setattr(worktrees.subprocess, "run", Recorder())

    # When
    with pytest.raises(StackError):
        worktrees.create(main=main_repo, branch="bad..name")

    # Then
    assert Registry.load().claimed_slot("bad..name") is None


def test_create_reports_failed_dependency_install(
    main_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a failing `uv sync` becomes a StackError with the recovery command."""

    # Given uv failing
    def fail_uv(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if cmd[0] == "uv":
            raise subprocess.CalledProcessError(1, cmd)
        return REAL_RUN(cmd, **kwargs)

    monkeypatch.setattr(worktrees.subprocess, "run", fail_uv)

    # When / Then
    with pytest.raises(StackError, match="uv sync --all-groups"):
        worktrees.create(main=main_repo, branch="feat-x")


def test_prune_keeps_entry_when_down_fails(
    main_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify a failed compose down keeps the entry so a later prune can retry."""
    # Given an entry whose checkout is gone and Docker failing
    _register(key="gone", slot=1, checkout=tmp_path / "gone")
    monkeypatch.setattr(worktrees.subprocess, "run", Recorder(lambda _cmd: 1))

    # When
    pruned = worktrees.prune(main=main_repo)

    # Then
    assert pruned == []
    assert Registry.load().claimed_slot("gone") == 1


def test_create_keeps_existing_claim_when_git_fails(
    main_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a failed `git worktree add` leaves a claim and entry made before the call."""
    # Given a claim for the branch's worktree path that predates the call
    path = main_repo / ".worktrees" / "bad..name"
    developers = [{"username": "dev-admin", "api_key": "kept"}]
    with Registry.locked() as registry:
        registry.assign_slot(key="other", checkout=main_repo / "other")
        slot = registry.assign_slot(key="bad..name", checkout=path)
        registry.upsert(
            Environment(
                key="bad..name",
                checkout=path,
                branch="bad..name",
                slot=slot,
                project=project_name(branch="bad..name"),
                ports=StackPorts.for_slot(slot),
                api_url="",
                api_url_from_containers="",
                healthz_url="",
                connection_sheet=path / ".dev" / "connection.md",
                keys_file=path / ".dev" / "api-keys.json",
                developers=developers,
            )
        )
    monkeypatch.setattr(worktrees.subprocess, "run", Recorder())

    # When
    with pytest.raises(StackError):
        worktrees.create(main=main_repo, branch="bad..name")

    # Then the claim and the entry's developers are untouched
    registry = Registry.load()
    assert registry.claimed_slot("bad..name") == slot
    assert registry.entries()["bad..name"].developers == developers


def test_teardown_refuses_locked_worktree_before_removing_volumes(
    main_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a locked worktree stops teardown before Docker removes its volumes."""
    # Given a registered worktree that git has locked
    recorder = Recorder()
    monkeypatch.setattr(worktrees.subprocess, "run", recorder)
    path = worktrees.create(main=main_repo, branch="feat-x")
    _git(main_repo, "worktree", "lock", str(path))
    recorder.calls.clear()

    # When
    with pytest.raises(StackError, match="locked"):
        worktrees.teardown(main=main_repo, target=path)

    # Then nothing was removed
    assert not recorder.calls
    assert path.exists()
    assert Registry.load().claimed_slot("feat-x") == 1


def test_prune_never_removes_an_entry_using_mains_project(
    main_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify prune skips a missing checkout whose entry names main's Compose project."""
    # Given a stray entry with a missing checkout that points at main's project
    _register(key="stray", slot=1, checkout=tmp_path / "gone", project=project_name(branch=None))
    recorder = Recorder()
    monkeypatch.setattr(worktrees.subprocess, "run", recorder)

    # When
    pruned = worktrees.prune(main=main_repo)

    # Then main's stack is untouched and the entry stays
    assert pruned == []
    assert not recorder.calls
    assert "stray" in Registry.load().entries()
