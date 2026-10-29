"""Unit tests for copying main's data into a worktree stack. No Docker or S3 runs."""

import subprocess
from pathlib import Path

import pytest
from scripts.devenv import copy as copy_module
from scripts.devenv.copy import MainNotInitializedError, copy_from_main


class RecordingRun:
    """Stand-in for `subprocess.run` that records commands and always succeeds.

    `docker compose port` answers 24103 for main's project and 24113 for any other.
    """

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(cmd))
        port = 24103 if "vapi-main" in cmd else 24113
        return subprocess.CompletedProcess(cmd, 0, stdout=f"127.0.0.1:{port}\n", stderr="")


class FakeProcess:
    """Stand-in for a `subprocess.Popen` process that exits with a fixed code."""

    def __init__(self, cmd: list[str], *, code: int) -> None:
        self.args = cmd
        self.stdout = None
        self._code = code

    def wait(self) -> int:
        return self._code


def test_copy_from_main_refuses_uninitialized_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify an empty main stack stops the copy with a pointer to `uv run duty up`."""
    # Given main's database has no schema yet
    fake = RecordingRun()
    popen_calls: list[list[str]] = []
    monkeypatch.setattr(copy_module.subprocess, "run", fake)
    monkeypatch.setattr(
        copy_module.subprocess, "Popen", lambda cmd, **_kwargs: popen_calls.append(cmd)
    )
    monkeypatch.setattr(copy_module, "is_fresh", lambda *, checkout, project: True)

    # When / Then
    with pytest.raises(MainNotInitializedError) as error:
        copy_from_main(main=tmp_path / "main", target=tmp_path / "wt", target_project="vapi-wt")
    commands = [*fake.calls, *popen_calls]
    assert "uv run duty up" in str(error.value)
    assert not any("pg_restore" in cmd for cmd in commands)
    assert any("postgres" in cmd and "s3" in cmd and "api" not in cmd for cmd in fake.calls)


def test_copy_from_main_copies_database_bucket_and_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify the dump is piped into restore, the bucket mirrored, and key files copied."""
    # Given an initialized main with a keys file and generated secrets
    main = tmp_path / "main"
    target = tmp_path / "wt"
    (main / ".dev").mkdir(parents=True)
    (main / ".dev" / "api-keys.json").write_text('{"id": "key"}')
    (main / ".dev" / "generated.env").write_text("VAPI_AUTHENTICATION_ENCRYPTION_KEY=abc\n")
    processes: list[FakeProcess] = []

    def popen(cmd: list[str], **_kwargs: object) -> FakeProcess:
        processes.append(FakeProcess(cmd, code=0))
        return processes[-1]

    mirrors: list[tuple[str, str]] = []
    fake = RecordingRun()
    monkeypatch.setattr(copy_module.subprocess, "run", fake)
    monkeypatch.setattr(copy_module.subprocess, "Popen", popen)
    monkeypatch.setattr(copy_module, "is_fresh", lambda *, checkout, project: False)
    monkeypatch.setattr(
        copy_module,
        "mirror_bucket",
        lambda *, source, destination, bucket: mirrors.append((source, destination)),
    )

    # When
    copy_from_main(main=main, target=target, target_project="vapi-wt")

    # Then
    assert "pg_dump" in processes[0].args
    assert "vapi-main" in processes[0].args
    assert "pg_restore" in processes[1].args
    assert "vapi-wt" in processes[1].args
    rewrites = [cmd for cmd in fake.calls if any("UPDATE s3_asset" in arg for arg in cmd)]
    assert len(rewrites) == 1
    assert "vapi-wt" in rewrites[0]
    assert (
        "UPDATE s3_asset SET public_url = replace(public_url, "
        "'http://127.0.0.1:24103/', 'http://127.0.0.1:24113/')"
    ) in rewrites[0]
    assert mirrors == [("http://127.0.0.1:24103", "http://127.0.0.1:24113")]
    assert (target / ".dev" / "api-keys.json").read_text() == '{"id": "key"}'
    assert (target / ".dev" / "api-keys.json").stat().st_mode & 0o777 == 0o600
    assert "abc" in (target / ".dev" / "generated.env").read_text()


def test_copy_from_main_fails_when_restore_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify a failed pg_restore stops the copy before the bucket mirror."""
    # Given
    monkeypatch.setattr(copy_module.subprocess, "run", RecordingRun())
    monkeypatch.setattr(
        copy_module.subprocess,
        "Popen",
        lambda cmd, **_kwargs: FakeProcess(cmd, code=1 if "pg_restore" in cmd else 0),
    )
    monkeypatch.setattr(copy_module, "is_fresh", lambda *, checkout, project: False)
    mirrors: list[str] = []
    monkeypatch.setattr(copy_module, "mirror_bucket", lambda **_kwargs: mirrors.append("called"))

    # When / Then
    with pytest.raises(copy_module.StackError, match="pg_restore"):
        copy_from_main(main=tmp_path / "main", target=tmp_path / "wt", target_project="vapi-wt")
    assert mirrors == []
