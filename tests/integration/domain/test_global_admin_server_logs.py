"""Test global admin server log endpoints."""

from __future__ import annotations

import io
import json
import zipfile
from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import HTTP_200_OK, HTTP_403_FORBIDDEN, HTTP_409_CONFLICT

from vapi.config import settings
from vapi.domain.urls import GlobalAdmin

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from httpx import AsyncClient

pytestmark = pytest.mark.anyio


def _line(level: str, message: str) -> str:
    """Build a JSON log line matching the app's file format."""
    return json.dumps(
        {"level": level, "timestamp": "2026-05-25T10:00:00Z", "name": "vapi", "message": message}
    )


async def test_tail_logs_returns_parsed_entries(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the admin receives parsed entries filtered by minimum level."""
    # Given a log file with mixed levels
    log_file = tmp_path / "app.log"
    log_file.write_text("\n".join([_line("INFO", "info-msg"), _line("ERROR", "error-msg")]))
    monkeypatch.setattr(settings.log, "file_path", log_file)

    # When tailing at ERROR minimum
    response = await client.get(
        build_url(GlobalAdmin.LOGS), headers=token_global_admin, params={"level": "ERROR"}
    )

    # Then only the ERROR entry is returned, parsed into structured fields
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert [entry["message"] for entry in data] == ["error-msg"]
    assert data[0]["level"] == "ERROR"


async def test_tail_logs_conflict_when_logging_disabled(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify tailing returns 409 when file logging is not configured."""
    # Given file logging is disabled
    monkeypatch.setattr(settings.log, "file_path", None)

    # When tailing
    response = await client.get(build_url(GlobalAdmin.LOGS), headers=token_global_admin)

    # Then the response is a 409 conflict
    assert response.status_code == HTTP_409_CONFLICT


async def test_tail_logs_forbidden_for_non_admin(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
) -> None:
    """Verify a non-global-admin caller is rejected."""
    # Given a non-global-admin token

    # When tailing
    response = await client.get(build_url(GlobalAdmin.LOGS), headers=token_company_admin)

    # Then access is forbidden
    assert response.status_code == HTTP_403_FORBIDDEN


async def test_download_logs_returns_zip(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the download returns a zip containing the active log file."""
    # Given an active log file
    log_file = tmp_path / "app.log"
    log_file.write_text(_line("INFO", "current"))
    monkeypatch.setattr(settings.log, "file_path", log_file)

    # When downloading the logs
    response = await client.get(build_url(GlobalAdmin.LOGS_DOWNLOAD), headers=token_global_admin)

    # Then a zip archive containing app.log is returned
    assert response.status_code == HTTP_200_OK
    assert response.headers["content-type"].startswith("application/zip")
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert "app.log" in archive.namelist()


async def test_download_logs_conflict_when_no_files(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the download returns 409 when no log files exist on disk."""
    # Given a configured path whose files do not exist
    monkeypatch.setattr(settings.log, "file_path", tmp_path / "app.log")

    # When downloading the logs
    response = await client.get(build_url(GlobalAdmin.LOGS_DOWNLOAD), headers=token_global_admin)

    # Then the response is a 409 conflict
    assert response.status_code == HTTP_409_CONFLICT
