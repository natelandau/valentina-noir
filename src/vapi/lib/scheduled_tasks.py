"""Tasks for SAQ.

This module contains the tasks for the SAQ plugin which are run at scheduled intervals.  Keep in
mind that the tasks are run in a separate process from the main application.
"""

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from saq.types import Context

if TYPE_CHECKING:
    from collections.abc import Callable

from vapi.config.base import BackupSettings
from vapi.domain.services import AWSS3Service
from vapi.utils.time import time_now

logger = logging.getLogger("vapi")

_LOG_EXTRA = {"component": "saq", "task": "purge_db_expired_items"}


async def _purge_archived_models() -> None:
    """Purge archived records older than 30 days across all tracked models.

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

    cutoff_date = time_now() - timedelta(days=30)

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
    """Purge audit log entries older than 30 days."""
    from vapi.db.sql_models.audit_log import AuditLog

    cutoff_date = time_now() - timedelta(days=30)

    try:
        deleted = await AuditLog.filter(date_modified__lt=cutoff_date).delete()
        logger.info(
            "Purge old AuditLogs.",
            extra={**_LOG_EXTRA, "num_purged": deleted},
        )
    except Exception:
        logger.exception("Failed to purge AuditLogs.", extra=_LOG_EXTRA)


async def _purge_s3_assets() -> None:
    """Purge archived S3 assets older than 30 days."""
    from vapi.db.sql_models.aws import S3Asset

    cutoff_date = time_now() - timedelta(days=30)

    try:
        assets = await S3Asset.filter(is_archived=True, date_modified__lt=cutoff_date)

        aws_service = AWSS3Service()
        purged = 0
        for asset in assets:
            try:
                await aws_service.delete_asset(asset)
                purged += 1
            except Exception:
                logger.exception(
                    "Failed to purge S3Asset %s.",
                    asset.id,
                    extra=_LOG_EXTRA,
                )

        logger.info(
            "Purge old S3Assets.",
            extra={**_LOG_EXTRA, "num_purged": purged},
        )
    except Exception:
        logger.exception("Failed to purge S3Assets.", extra=_LOG_EXTRA)


async def _purge_chargen_sessions() -> None:
    """Purge expired chargen sessions and their linked characters."""
    from vapi.db.sql_models.chargen_session import ChargenSession

    try:
        expired_sessions = await ChargenSession.filter(expires_at__lt=time_now()).prefetch_related(
            "characters"
        )

        for session in expired_sessions:
            for character in session.characters:
                try:
                    await character.delete()
                except Exception:
                    logger.exception(
                        "Failed to delete character %s from session %s.",
                        character.id,
                        session.id,
                        extra=_LOG_EXTRA,
                    )
            await session.delete()

        logger.info(
            "Purge expired ChargenSessions.",
            extra={**_LOG_EXTRA, "num_purged": len(expired_sessions)},
        )
    except Exception:
        logger.exception(
            "Failed to purge ChargenSessions.",
            extra=_LOG_EXTRA,
        )


async def _purge_temporary_characters() -> None:
    """Purge temporary non-chargen characters not modified in the last 24 hours."""
    from vapi.db.sql_models.character import Character

    cutoff_date = time_now() - timedelta(hours=24)

    try:
        characters = await Character.filter(
            is_chargen=False,
            is_temporary=True,
            date_modified__lt=cutoff_date,
        )
        purged = 0
        for character in characters:
            try:
                await character.delete()
                purged += 1
            except Exception:
                logger.exception(
                    "Failed to delete temporary Character %s.",
                    character.id,
                    extra=_LOG_EXTRA,
                )

        logger.info(
            "Purge expired temporary Characters.",
            extra={**_LOG_EXTRA, "num_purged": purged},
        )
    except Exception:
        logger.exception(
            "Failed to purge temporary Characters.",
            extra=_LOG_EXTRA,
        )


def _parse_dated_keys(keys: list[str]) -> list[tuple[date, str]]:
    """Parse S3 keys into (date, key) pairs, silently skipping unparsable keys.

    Args:
        keys: S3 object keys in the form ``prefix/YYYY-MM-DD.dump``.

    Returns:
        Parsed pairs sorted newest-first.
    """
    dated: list[tuple[date, str]] = []
    for key in keys:
        filename = key.rsplit("/", 1)[-1]
        date_str = filename.removesuffix(".dump")
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

    # Daily: keep the most recent N
    keep.update(key for _, key in dated[: backup_settings.retain_daily])

    # Weekly: oldest backup from each of the N most recent ISO weeks
    if backup_settings.retain_weekly > 0:
        keep |= _keep_oldest_per_bucket(
            dated,
            lambda d: (d.isocalendar()[0], d.isocalendar()[1]),
            backup_settings.retain_weekly,
        )

    # Monthly: oldest backup from each of the N most recent months
    if backup_settings.retain_monthly > 0:
        keep |= _keep_oldest_per_bucket(
            dated,
            lambda d: (d.year, d.month),
            backup_settings.retain_monthly,
        )

    # Yearly: oldest backup from each of the N most recent years
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
    from vapi.lib.database import init_tortoise

    logger.info("Start database cleanup.", extra=_LOG_EXTRA)

    await init_tortoise()

    await _purge_archived_models()
    await _purge_audit_logs()
    await _purge_s3_assets()
    await _purge_chargen_sessions()
    await _purge_temporary_characters()

    logger.info(
        "Database cleanup completed.",
        extra=_LOG_EXTRA,
    )
