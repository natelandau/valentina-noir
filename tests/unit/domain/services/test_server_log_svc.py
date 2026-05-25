"""Test the server log service."""

import json
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


def test_tail_entries_filters_by_minimum_level(tmp_path: Path, monkeypatch) -> None:
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


def test_tail_entries_respects_limit_and_newest_first(tmp_path: Path, monkeypatch) -> None:
    """Verify the limit caps results and the newest entries come first."""
    # Given a log file with three INFO lines in chronological order
    log_file = tmp_path / "app.log"
    log_file.write_text("\n".join([_line("INFO", "1"), _line("INFO", "2"), _line("INFO", "3")]))
    monkeypatch.setattr(settings.log, "file_path", log_file)

    # When tailing with a limit of 2
    entries = ServerLogService().tail_entries(level=LogLevel.INFO, limit=2)

    # Then the two most recent lines are returned, newest first
    assert [e.message for e in entries] == ["3", "2"]


def test_tail_entries_unparseable_line_always_included(tmp_path: Path, monkeypatch) -> None:
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


def test_tail_entries_missing_file_returns_empty(tmp_path: Path, monkeypatch) -> None:
    """Verify a configured-but-absent log file yields no entries."""
    # Given a configured path that does not exist on disk
    monkeypatch.setattr(settings.log, "file_path", tmp_path / "absent.log")

    # When tailing
    entries = ServerLogService().tail_entries(level=LogLevel.INFO, limit=100)

    # Then the result is empty
    assert entries == []


def test_tail_entries_no_file_path_raises_conflict(monkeypatch) -> None:
    """Verify tailing without file logging configured raises ConflictError."""
    # Given file logging is disabled
    monkeypatch.setattr(settings.log, "file_path", None)

    # When tailing, Then a ConflictError is raised
    with pytest.raises(ConflictError):
        ServerLogService().tail_entries(level=LogLevel.INFO, limit=100)
