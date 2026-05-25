"""Read and package the application's on-disk log files for global admins."""

import zipfile
from collections import deque
from pathlib import Path
from tempfile import NamedTemporaryFile

from vapi.config import settings
from vapi.constants import LogLevel
from vapi.domain.services.server_log_dto import LogEntry
from vapi.lib.exceptions import ConflictError

# Numeric ranks for minimum-level (>=) filtering. TRACE is not a native logging
# level, so ordering is defined explicitly rather than via the logging module.
_LEVEL_RANK: dict[str, int] = {
    "TRACE": 5,
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


class ServerLogService:
    """Read and package the application's on-disk log files."""

    def _base_path(self) -> Path:
        """Resolve the configured active log file path or signal it is disabled."""
        if settings.log.file_path is None:
            raise ConflictError(detail="File logging is not enabled.")
        return settings.log.file_path.expanduser().resolve()

    @staticmethod
    def _meets_threshold(level: str | None, threshold: int) -> bool:
        """Return True when a parsed entry's level meets the minimum rank."""
        if level is None:
            return False
        return _LEVEL_RANK.get(level.upper(), 0) >= threshold

    def tail_entries(self, *, level: LogLevel, limit: int) -> list[LogEntry]:
        """Return up to `limit` recent entries at or above `level`, newest first.

        Reads only the active log file, since the most recent entries live there.
        Unparseable lines are always included so corruption is visible to admins.

        Args:
            level: The minimum log level to include in results.
            limit: The maximum number of entries to return.

        Returns:
            list[LogEntry]: Recent log entries in reverse-chronological order.
        """
        base = self._base_path()
        if not base.exists():
            return []

        threshold = _LEVEL_RANK.get(level.value, 0)
        matched: deque[LogEntry] = deque(maxlen=limit)
        with base.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                entry = LogEntry.from_line(line)
                if entry.raw is not None or self._meets_threshold(entry.level, threshold):
                    matched.append(entry)

        return list(reversed(matched))

    def _existing_files(self) -> list[Path]:
        """Return the active log file plus any rotated backups that exist on disk."""
        base = self._base_path()
        # Backups .1 and .2 mirror RotatingFileHandler(backupCount=2) in lib/log_config.py
        candidates = [base, *(base.with_name(f"{base.name}.{i}") for i in (1, 2))]
        return [path for path in candidates if path.exists()]

    def build_archive(self) -> Path:
        """Zip the active and rotated log files into a temp file and return its path.

        The caller is responsible for deleting the returned file once it has been
        streamed to the client.

        Raises:
            ConflictError: If file logging is disabled or no log files exist on disk.
        """
        files = self._existing_files()
        if not files:
            raise ConflictError(detail="No log files found on disk.")

        tmp = NamedTemporaryFile(suffix=".zip", delete=False)  # noqa: SIM115
        tmp.close()
        archive_path = Path(tmp.name)
        try:
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in files:
                    archive.write(path, arcname=path.name)
        except Exception:
            archive_path.unlink(missing_ok=True)
            raise
        return archive_path
