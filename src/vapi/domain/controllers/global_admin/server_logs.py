"""Global admin server log controllers."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from litestar.background_tasks import BackgroundTask
from litestar.controller import Controller
from litestar.handlers import get
from litestar.params import Parameter
from litestar.response import File

from vapi.config import settings
from vapi.constants import LogLevel
from vapi.domain import urls
from vapi.domain.services.server_log_dto import LogEntry
from vapi.domain.services.server_log_svc import ServerLogService
from vapi.lib.guards import global_admin_guard
from vapi.openapi.tags import APITags

from . import server_logs_docs as docs


def _unlink_archive(path: Path) -> None:
    """Delete the temporary log archive after it has been streamed to the client."""
    path.unlink(missing_ok=True)


class GlobalAdminServerLogsController(Controller):
    """Global admin controller for inspecting on-disk server logs."""

    tags = [APITags.GLOBAL_ADMIN.name]
    guards = [global_admin_guard]

    @get(
        path=urls.GlobalAdmin.LOGS,
        summary="Tail server logs",
        operation_id="globalAdminTailServerLogs",
        description=docs.TAIL_LOGS_DESCRIPTION,
        cache=False,
    )
    async def tail_logs(
        self,
        level: LogLevel | None = None,
        limit: Annotated[int, Parameter(ge=1, le=500)] = 100,
    ) -> list[LogEntry]:
        """Return the most recent log entries at or above the given level."""
        effective_level = level if level is not None else settings.log.level
        return await asyncio.to_thread(
            ServerLogService().tail_entries, level=effective_level, limit=limit
        )

    @get(
        path=urls.GlobalAdmin.LOGS_DOWNLOAD,
        summary="Download server logs",
        operation_id="globalAdminDownloadServerLogs",
        description=docs.DOWNLOAD_LOGS_DESCRIPTION,
        cache=False,
    )
    async def download_logs(self) -> File:
        """Stream a zip archive of the active and rotated log files."""
        archive_path = await asyncio.to_thread(ServerLogService().build_archive)
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        return File(
            path=archive_path,
            filename=f"vapi-logs-{timestamp}.zip",
            media_type="application/zip",
            content_disposition_type="attachment",
            background=BackgroundTask(_unlink_archive, archive_path),
        )
