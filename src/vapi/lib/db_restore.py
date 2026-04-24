"""Database restore service: drop the database and pg_restore a pg_dump -Fc backup."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from vapi.config import settings
from vapi.constants import BACKUP_S3_PREFIX
from vapi.domain.services.aws_service import AWSS3Service
from vapi.lib.database import drop_and_recreate_database, pg_subprocess_env
from vapi.lib.exceptions import (
    AWSS3Error,
    DatabaseRestoreError,
    MissingConfigurationError,
)

logger = logging.getLogger("vapi")

_LOG_EXTRA = {"component": "db_restore"}
_CREDS_HINT = (
    "AWS credentials not configured. "
    "Use --file to restore from a local dump, or set VAPI_AWS_* in your environment."
)
_EMPTY_PREFIX_HINT = (
    f"No backups found in S3 under {BACKUP_S3_PREFIX}. Run the backup task or provide --file."
)


@dataclass(frozen=True)
class LocalFileSource:
    """A dump provided as a path on the local filesystem."""

    path: Path


@dataclass(frozen=True)
class S3Source:
    """A dump stored in S3. ``key=None`` means use the most recent backup."""

    key: str | None


RestoreSource = LocalFileSource | S3Source


class DatabaseRestoreService:
    """Restore a PostgreSQL database from a ``pg_dump -Fc`` backup."""

    async def resolve_source(self, source: RestoreSource) -> tuple[Path, bool]:
        """Resolve a RestoreSource to a local dump path.

        Args:
            source: Either a LocalFileSource (user-supplied path) or an S3Source
                (bucket key, or None for the most recent backup).

        Returns:
            A tuple of (dump_path, should_cleanup). ``should_cleanup`` is True
            only when the dump was downloaded to a temp file by this call.
        """
        if isinstance(source, LocalFileSource):
            return source.path, False

        try:
            aws = AWSS3Service()
        except MissingConfigurationError as e:
            raise DatabaseRestoreError(_CREDS_HINT) from e

        if source.key is None:
            keys = await aws.list_keys(prefix=BACKUP_S3_PREFIX)
            if not keys:
                raise DatabaseRestoreError(_EMPTY_PREFIX_HINT)
            selected_key = max(keys)
        else:
            selected_key = source.key

        with NamedTemporaryFile(suffix=".dump", delete=False) as tmp_file:
            dest_path = Path(tmp_file.name)

        logger.info(
            "Downloading backup from S3.",
            extra={**_LOG_EXTRA, "s3_key": selected_key, "dest_path": str(dest_path)},
        )
        try:
            await aws.download_file(key=selected_key, dest_path=dest_path)
        except AWSS3Error as e:
            msg = f"Failed to download backup: {e}"
            dest_path.unlink(missing_ok=True)  # noqa: ASYNC240
            raise DatabaseRestoreError(msg) from e

        return dest_path, True

    async def run(self, source: RestoreSource) -> None:
        """Restore the database from the given dump source.

        The database is dropped and recreated, then ``pg_restore`` loads the
        dump into the empty database. Temp files created by this call (S3
        downloads) are cleaned up; a caller-provided local file is never
        deleted.

        Raises:
            DatabaseRestoreError: If dump download, drop/recreate, or
                pg_restore fails.
        """
        dump_path, should_cleanup = await self.resolve_source(source)

        try:
            logger.info(
                "Dropping and recreating target database.",
                extra={**_LOG_EXTRA, "database": settings.postgres.database},
            )
            await drop_and_recreate_database()

            pg = settings.postgres
            logger.info(
                "Running pg_restore.",
                extra={**_LOG_EXTRA, "dump_path": str(dump_path)},
            )
            process = await asyncio.create_subprocess_exec(
                "pg_restore",
                "-h",
                pg.host,
                "-p",
                str(pg.port),
                "-U",
                pg.user,
                "-d",
                pg.database,
                "--no-owner",
                "--no-privileges",
                str(dump_path),
                env=pg_subprocess_env(),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await process.communicate()

            if process.returncode != 0:
                stderr_text = stderr.decode().strip()
                logger.error(
                    "pg_restore failed.",
                    extra={**_LOG_EXTRA, "stderr": stderr_text},
                )
                msg = f"pg_restore exited with code {process.returncode}: {stderr_text}"
                raise DatabaseRestoreError(msg)

            logger.info("Database restore complete.", extra=_LOG_EXTRA)
        finally:
            if should_cleanup:
                dump_path.unlink(missing_ok=True)
