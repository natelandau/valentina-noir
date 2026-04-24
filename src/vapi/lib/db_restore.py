"""Database restore service: drop the database and pg_restore a pg_dump -Fc backup."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from vapi.domain.services.aws_service import AWSS3Service
from vapi.lib.exceptions import (
    AWSS3Error,
    DatabaseRestoreError,
    MissingConfigurationError,
)

logger = logging.getLogger("vapi")

_LOG_EXTRA = {"component": "db_restore"}
_BACKUP_PREFIX = "db_backups/"
_CREDS_HINT = (
    "AWS credentials not configured. "
    "Use --file to restore from a local dump, or set VAPI_AWS_* in your environment."
)
_EMPTY_PREFIX_HINT = (
    f"No backups found in S3 under {_BACKUP_PREFIX}. Run the backup task or provide --file."
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

    async def _resolve_source(self, source: RestoreSource) -> tuple[Path, bool]:
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
            keys = await aws.list_keys(prefix=_BACKUP_PREFIX)
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
            # Clean up the empty temp file we created before re-raising.
            msg = f"Failed to download backup: {e}"
            dest_path.unlink(missing_ok=True)  # noqa: ASYNC240
            raise DatabaseRestoreError(msg) from e

        return dest_path, True
