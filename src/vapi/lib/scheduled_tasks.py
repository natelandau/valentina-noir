"""Tasks for SAQ.

This module contains the tasks for the SAQ plugin which are run at scheduled intervals.  Keep in
mind that the tasks are run in a separate process from the main application.
"""

import asyncio
import contextlib
import logging
from datetime import date, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any

from saq.types import Context

if TYPE_CHECKING:
    from collections.abc import Callable

from vapi.config.base import BackupSettings, settings
from vapi.constants import AUDIT_LOG_RETENTION_DAYS, BACKUP_S3_PREFIX
from vapi.domain.services import AWSS3Service
from vapi.lib.database import pg_subprocess_env
from vapi.lib.exceptions import AWSS3Error, MissingConfigurationError
from vapi.utils.time import time_now

logger = logging.getLogger("vapi")

_LOG_EXTRA = {"component": "saq", "task": "purge_db_expired_items"}
_ARCHIVED_RETENTION_DAYS = 30
_TEMPORARY_CHARACTER_RETENTION_HOURS = 24


async def _purge_archived_models() -> None:
    """Purge archived records older than the retention window across all tracked models.

    S3Asset is excluded here because _purge_s3_assets handles it separately,
    ensuring each asset's backing object is deleted from AWS before removing
    the DB record.
    """
    from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
    from vapi.db.sql_models.character import Character, CharacterInventory
    from vapi.db.sql_models.character_concept import CharacterConcept
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.diceroll import DiceRoll
    from vapi.db.sql_models.dictionary import DictionaryTerm
    from vapi.db.sql_models.notes import Note
    from vapi.db.sql_models.quickroll import QuickRoll
    from vapi.db.sql_models.user import User

    cutoff_date = time_now() - timedelta(days=_ARCHIVED_RETENTION_DAYS)

    # Order child-first to respect FK dependencies
    for model in [
        DiceRoll,
        DictionaryTerm,
        Note,
        QuickRoll,
        CharacterInventory,
        Character,
        CampaignChapter,
        CampaignBook,
        Campaign,
        CharacterConcept,
        User,
        Company,
    ]:
        try:
            deleted = await model.filter(is_archived=True, date_modified__lt=cutoff_date).delete()
            logger.info(
                "Purge old %s.",
                model.__name__,
                extra={**_LOG_EXTRA, "num_purged": deleted},
            )
        except Exception:
            logger.exception(
                "Failed to purge %s.",
                model.__name__,
                extra=_LOG_EXTRA,
            )


async def _purge_audit_logs() -> None:
    """Purge audit log entries older than the configured retention window."""
    from vapi.db.sql_models.audit_log import AuditLog

    cutoff_date = time_now() - timedelta(days=AUDIT_LOG_RETENTION_DAYS)

    try:
        deleted = await AuditLog.filter(date_created__lt=cutoff_date).delete()
        logger.info(
            "Purge old AuditLogs.",
            extra={**_LOG_EXTRA, "num_purged": deleted},
        )
    except Exception:
        logger.exception("Failed to purge AuditLogs.", extra=_LOG_EXTRA)


async def _purge_s3_assets() -> None:
    """Purge archived S3 assets older than the retention window."""
    from vapi.db.sql_models.aws import S3Asset

    cutoff_date = time_now() - timedelta(days=_ARCHIVED_RETENTION_DAYS)

    try:
        aws_service = AWSS3Service()
    except MissingConfigurationError:
        logger.warning(
            "AWS credentials not configured, skipping S3Asset purge.",
            extra=_LOG_EXTRA,
        )
        return

    try:
        assets = await S3Asset.filter(is_archived=True, date_modified__lt=cutoff_date)
    except Exception:
        logger.exception("Failed to purge S3Assets.", extra=_LOG_EXTRA)
        return

    results = await asyncio.gather(
        *(aws_service.delete_asset(asset) for asset in assets),
        return_exceptions=True,
    )
    failed = 0
    for asset, result in zip(assets, results, strict=True):
        if isinstance(result, BaseException):
            failed += 1
            logger.exception(
                "Failed to purge S3Asset %s.",
                asset.id,
                exc_info=result,
                extra=_LOG_EXTRA,
            )
    purged = len(assets) - failed

    logger.info(
        "Purge old S3Assets.",
        extra={**_LOG_EXTRA, "num_purged": purged},
    )


async def _purge_chargen_sessions() -> None:
    """Purge expired chargen sessions and their linked characters."""
    from vapi.db.sql_models.chargen_session import ChargenSession

    try:
        expired_sessions = await ChargenSession.filter(expires_at__lt=time_now()).prefetch_related(
            "characters"
        )
    except Exception:
        logger.exception("Failed to purge ChargenSessions.", extra=_LOG_EXTRA)
        return

    for session in expired_sessions:
        char_results = await asyncio.gather(
            *(character.delete() for character in session.characters),
            return_exceptions=True,
        )
        for character, result in zip(session.characters, char_results, strict=True):
            if isinstance(result, BaseException):
                logger.exception(
                    "Failed to delete character %s from session %s.",
                    character.id,
                    session.id,
                    exc_info=result,
                    extra=_LOG_EXTRA,
                )
        try:
            await session.delete()
        except Exception:
            logger.exception(
                "Failed to delete ChargenSession %s.",
                session.id,
                extra=_LOG_EXTRA,
            )

    logger.info(
        "Purge expired ChargenSessions.",
        extra={**_LOG_EXTRA, "num_purged": len(expired_sessions)},
    )


async def _purge_temporary_characters() -> None:
    """Purge temporary non-chargen characters not modified in the last 24 hours."""
    from vapi.db.sql_models.character import Character

    cutoff_date = time_now() - timedelta(hours=_TEMPORARY_CHARACTER_RETENTION_HOURS)

    try:
        deleted = await Character.filter(
            is_chargen=False,
            is_temporary=True,
            date_modified__lt=cutoff_date,
        ).delete()
        logger.info(
            "Purge expired temporary Characters.",
            extra={**_LOG_EXTRA, "num_purged": deleted},
        )
    except Exception:
        logger.exception("Failed to purge temporary Characters.", extra=_LOG_EXTRA)


def _parse_dated_keys(keys: list[str]) -> list[tuple[date, str]]:
    """Parse S3 keys into (date, key) pairs, silently skipping unparsable keys.

    Args:
        keys: S3 object keys in the form ``prefix/YYYY-MM-DD.dump``.

    Returns:
        Parsed pairs sorted newest-first.
    """
    dated: list[tuple[date, str]] = []
    for key in keys:
        date_str = Path(key).stem
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            continue
        dated.append((d, key))

    dated.sort(key=lambda x: x[0], reverse=True)
    return dated


def _keep_oldest_per_bucket(
    dated: list[tuple[date, str]],
    bucket_fn: "Callable[[date], Any]",
    retain: int,
) -> set[str]:
    """Keep the oldest backup from each of the N most recent buckets.

    Args:
        dated: (date, key) pairs sorted newest-first.
        bucket_fn: Maps a date to a hashable bucket identifier.
        retain: Number of most-recent buckets to keep.

    Returns:
        Keys that should be retained.
    """
    buckets: dict[Any, list[tuple[Any, str]]] = {}
    for d, key in dated:
        buckets.setdefault(bucket_fn(d), []).append((d, key))

    kept: set[str] = set()
    for bucket in sorted(buckets.keys(), reverse=True)[:retain]:
        oldest = min(buckets[bucket], key=lambda x: x[0])
        kept.add(oldest[1])
    return kept


def _compute_backups_to_delete(keys: list[str], backup_settings: BackupSettings) -> list[str]:
    """Determine which backup keys to delete based on retention policy.

    Each key is expected to match the pattern ``db_backups/YYYY-MM-DD.dump``.
    Keys that do not match are silently ignored (never returned for deletion).

    Args:
        keys: S3 object keys to evaluate.
        backup_settings: Retention configuration.

    Returns:
        Keys that should be deleted.
    """
    dated = _parse_dated_keys(keys)
    if not dated:
        return []

    keep: set[str] = set()
    keep.update(key for _, key in dated[: backup_settings.retain_daily])

    if backup_settings.retain_weekly > 0:
        keep |= _keep_oldest_per_bucket(
            dated,
            lambda d: (d.isocalendar()[0], d.isocalendar()[1]),
            backup_settings.retain_weekly,
        )

    if backup_settings.retain_monthly > 0:
        keep |= _keep_oldest_per_bucket(
            dated,
            lambda d: (d.year, d.month),
            backup_settings.retain_monthly,
        )

    if backup_settings.retain_yearly > 0:
        keep |= _keep_oldest_per_bucket(
            dated,
            lambda d: d.year,
            backup_settings.retain_yearly,
        )

    return [key for _, key in dated if key not in keep]


async def purge_db_expired_items(_: Context) -> None:
    """Purge expired and archived data across all database models, S3 assets, and sessions.

    Delegate to focused helper functions for each cleanup concern. Each helper
    handles its own imports, error handling, and logging so that a failure in one
    does not prevent the others from running.
    """
    from tortoise import Tortoise

    from vapi.lib.database import init_tortoise

    logger.info("Start database cleanup.", extra=_LOG_EXTRA)

    await init_tortoise()

    try:
        await _purge_archived_models()
        await _purge_audit_logs()
        await _purge_s3_assets()
        await _purge_chargen_sessions()
        await _purge_temporary_characters()
    finally:
        await Tortoise.close_connections()

    logger.info(
        "Database cleanup completed.",
        extra=_LOG_EXTRA,
    )


_BACKUP_LOG_EXTRA = {"component": "saq", "task": "backup_database"}


async def backup_database(_: Context) -> None:
    """Create a PostgreSQL backup, upload to S3, and prune old backups per retention policy.

    Runs pg_dump in custom format, streams the dump to S3 under db_backups/,
    then applies retention rules to delete expired backups. Each stage is
    isolated so that a failure in pruning does not affect the backup itself.
    """
    if not settings.backup.enabled:
        logger.info("Database backup is disabled, skipping.", extra=_BACKUP_LOG_EXTRA)
        return

    try:
        aws_service = AWSS3Service()
    except MissingConfigurationError:
        logger.warning(
            "AWS credentials not configured, skipping database backup.",
            extra=_BACKUP_LOG_EXTRA,
        )
        return

    logger.info("Starting database backup.", extra=_BACKUP_LOG_EXTRA)

    tmp_path: str | None = None
    try:
        with NamedTemporaryFile(suffix=".dump", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        process = await asyncio.create_subprocess_exec(
            "pg_dump",
            "-Fc",
            "-h",
            settings.postgres.host,
            "-p",
            str(settings.postgres.port),
            "-U",
            settings.postgres.user,
            "-d",
            settings.postgres.database,
            "-f",
            tmp_path,
            env=pg_subprocess_env(),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(
                "pg_dump failed: %s",
                stderr.decode().strip(),
                extra=_BACKUP_LOG_EXTRA,
            )
            return

        stat_result = await asyncio.to_thread(Path(tmp_path).stat)
        file_size = stat_result.st_size
        logger.info(
            "Database dump complete.",
            extra={**_BACKUP_LOG_EXTRA, "file_size_bytes": file_size},
        )

        s3_key = f"{BACKUP_S3_PREFIX}{time_now().strftime('%Y-%m-%d')}.dump"

        try:
            await aws_service.upload_file(
                key=s3_key,
                file_path=Path(tmp_path),
                content_type="application/octet-stream",
            )
        except AWSS3Error:
            logger.exception("Failed to upload backup to S3.", extra=_BACKUP_LOG_EXTRA)
            return

        logger.info("Backup uploaded to S3.", extra={**_BACKUP_LOG_EXTRA, "s3_key": s3_key})

        try:
            all_keys = await aws_service.list_keys(prefix=BACKUP_S3_PREFIX)
        except AWSS3Error:
            logger.exception("Failed to list backups during pruning.", extra=_BACKUP_LOG_EXTRA)
            return

        to_delete = _compute_backups_to_delete(all_keys, settings.backup)
        results = await asyncio.gather(
            *(aws_service.delete_key(key=key) for key in to_delete),
            return_exceptions=True,
        )
        for key, result in zip(to_delete, results, strict=True):
            if isinstance(result, BaseException):
                logger.exception(
                    "Failed to delete expired backup %s.",
                    key,
                    exc_info=result,
                    extra=_BACKUP_LOG_EXTRA,
                )

        logger.info(
            "Backup retention pruning complete.",
            extra={**_BACKUP_LOG_EXTRA, "num_deleted": len(to_delete)},
        )

    finally:
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                await asyncio.to_thread(Path(tmp_path).unlink, missing_ok=True)
