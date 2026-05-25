"""Test the server log service."""

import json
import zipfile
from pathlib import Path

import pytest

from vapi.config import settings
from vapi.constants import LogLevel
from vapi.domain.services.server_log_svc import ServerLogService
from vapi.lib.exceptions import ConflictError


def _line(level: str, message: str) -> str:
    """Build a JSON log line matching the app's file format."""
    return json.dumps(
        {"level": level, "timestamp": "2026-05-25T10:00:00Z", "name": "vapi", "message": message}
    )


def test_tail_entries_filters_by_minimum_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify only entries at or above the requested level are returned."""
    # Given a log file with mixed levels
    log_file = tmp_path / "app.log"
    log_file.write_text(
        "\n".join([_line("DEBUG", "d"), _line("INFO", "i"), _line("ERROR", "e")]) + "\n"
    )
    monkeypatch.setattr(settings.log, "file_path", log_file)

    # When tailing at WARNING minimum
    entries = ServerLogService().tail_entries(level=LogLevel.WARNING, limit=100)

    # Then only ERROR (>= WARNING) is returned
    assert [e.message for e in entries] == ["e"]


def test_tail_entries_respects_limit_and_newest_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the limit caps results and the newest entries come first."""
    # Given a log file with three INFO lines in chronological order
    log_file = tmp_path / "app.log"
    log_file.write_text("\n".join([_line("INFO", "1"), _line("INFO", "2"), _line("INFO", "3")]))
    monkeypatch.setattr(settings.log, "file_path", log_file)

    # When tailing with a limit of 2
    entries = ServerLogService().tail_entries(level=LogLevel.INFO, limit=2)

    # Then the two most recent lines are returned, newest first
    assert [e.message for e in entries] == ["3", "2"]


def test_tail_entries_unparsable_line_always_included(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify malformed lines are surfaced as raw regardless of the level filter."""
    # Given a log file containing a non-JSON line
    log_file = tmp_path / "app.log"
    log_file.write_text("not json\n" + _line("INFO", "ok"))
    monkeypatch.setattr(settings.log, "file_path", log_file)

    # When tailing at ERROR minimum
    entries = ServerLogService().tail_entries(level=LogLevel.ERROR, limit=100)

    # Then the raw line is still present even though INFO was filtered out
    raws = [e.raw for e in entries if e.raw is not None]
    assert raws == ["not json"]


def test_tail_entries_missing_file_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a configured-but-absent log file yields no entries."""
    # Given a configured path that does not exist on disk
    monkeypatch.setattr(settings.log, "file_path", tmp_path / "absent.log")

    # When tailing
    entries = ServerLogService().tail_entries(level=LogLevel.INFO, limit=100)

    # Then the result is empty
    assert entries == []


def test_tail_entries_no_file_path_raises_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify tailing without file logging configured raises ConflictError."""
    # Given file logging is disabled
    monkeypatch.setattr(settings.log, "file_path", None)

    # When tailing, Then a ConflictError is raised
    with pytest.raises(ConflictError):
        ServerLogService().tail_entries(level=LogLevel.INFO, limit=100)


def test_build_archive_zips_active_and_rotated_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the archive contains the active file and existing rotated backups."""
    # Given an active log file and one rotated backup (but no .2)
    active = tmp_path / "app.log"
    active.write_text(_line("INFO", "current"))
    (tmp_path / "app.log.1").write_text(_line("INFO", "older"))
    monkeypatch.setattr(settings.log, "file_path", active)

    # When building the archive
    archive_path = ServerLogService().build_archive()

    # Then the zip holds exactly the files that exist on disk
    try:
        with zipfile.ZipFile(archive_path) as archive:
            assert sorted(archive.namelist()) == ["app.log", "app.log.1"]
            assert archive.read("app.log").decode() == _line("INFO", "current")
    finally:
        archive_path.unlink(missing_ok=True)


def test_build_archive_no_files_raises_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a configured path with no files on disk raises ConflictError."""
    # Given a configured path whose files do not exist
    monkeypatch.setattr(settings.log, "file_path", tmp_path / "app.log")

    # When building the archive, Then a ConflictError is raised
    with pytest.raises(ConflictError):
        ServerLogService().build_archive()


def test_build_archive_no_file_path_raises_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify building an archive without file logging configured raises ConflictError."""
    # Given file logging is disabled
    monkeypatch.setattr(settings.log, "file_path", None)

    # When building the archive, Then a ConflictError is raised
    with pytest.raises(ConflictError):
        ServerLogService().build_archive()


def test_tail_entries_does_not_crash_on_non_string_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a numeric level value is surfaced instead of crashing the tail."""
    # Given a log line whose level is numeric (the formatter can emit this)
    log_file = tmp_path / "app.log"
    log_file.write_text(json.dumps({"level": 42, "message": "weird"}))
    monkeypatch.setattr(settings.log, "file_path", log_file)

    # When tailing
    entries = ServerLogService().tail_entries(level=LogLevel.INFO, limit=100)

    # Then the entry is surfaced as an unknown-level entry rather than raising
    assert [e.message for e in entries] == ["weird"]


def test_tail_entries_includes_unknown_level_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify entries with an unrecognized level name are surfaced, not dropped."""
    # Given a log line with a custom level name not in the rank table
    log_file = tmp_path / "app.log"
    log_file.write_text(json.dumps({"level": "NOTICE", "message": "heads up"}))
    monkeypatch.setattr(settings.log, "file_path", log_file)

    # When tailing at a high threshold
    entries = ServerLogService().tail_entries(level=LogLevel.ERROR, limit=100)

    # Then the unknown-level entry is still returned
    assert [e.message for e in entries] == ["heads up"]


def test_tail_entries_raw_lines_do_not_evict_matched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify unparsable lines do not consume the matched-entry limit budget."""
    # Given two ERROR entries followed by three unparsable lines
    log_file = tmp_path / "app.log"
    log_file.write_text(
        "\n".join([_line("ERROR", "e1"), _line("ERROR", "e2"), "junk1", "junk2", "junk3"])
    )
    monkeypatch.setattr(settings.log, "file_path", log_file)

    # When tailing at ERROR with a limit of 2
    entries = ServerLogService().tail_entries(level=LogLevel.ERROR, limit=2)

    # Then both ERROR entries survive (raw lines did not evict them from the limit)
    messages = [e.message for e in entries if e.message is not None]
    raws = [e.raw for e in entries if e.raw is not None]
    assert "e1" in messages
    assert "e2" in messages
    assert len(raws) >= 1


def test_tail_entries_replaces_invalid_utf8_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a non-UTF-8 byte does not crash the tail."""
    # Given a log file containing an invalid UTF-8 byte sequence
    log_file = tmp_path / "app.log"
    log_file.write_bytes(b"\xff\xfe not utf8\n" + _line("ERROR", "ok").encode())
    monkeypatch.setattr(settings.log, "file_path", log_file)

    # When tailing
    entries = ServerLogService().tail_entries(level=LogLevel.ERROR, limit=100)

    # Then the request succeeds and the valid ERROR entry is present
    assert any(e.message == "ok" for e in entries)
