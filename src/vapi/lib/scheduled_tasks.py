"""Tasks for SAQ.

This module contains the tasks for the SAQ plugin which are run at scheduled intervals.  Keep in
mind that the tasks are run in a separate process from the main application.
"""

import logging
from datetime import timedelta

from saq.types import Context

from vapi.domain.services import AWSS3Service
from vapi.utils.time import time_now

logger = logging.getLogger("vapi")


async def _purge_archived_models() -> None:
    """Purge archived documents older than 30 days across all tracked models."""
    from beanie.odm.operators.find.comparison import LT

    from vapi.db.models import (
        Campaign,
        CampaignBook,
        CampaignChapter,
        Character,
        CharacterConcept,
        CharacterInventory,
        Company,
        DiceRoll,
        DictionaryTerm,
        Note,
        QuickRoll,
        Trait,
        User,
    )

    cutoff_date = time_now() - timedelta(days=30)

    for model in [
        Campaign,
        CampaignBook,
        CampaignChapter,
        Character,
        CharacterConcept,
        CharacterInventory,
        Company,
        DiceRoll,
        DictionaryTerm,
        Note,
        QuickRoll,
        Trait,
        User,
    ]:
        try:
            deleted = await model.find(
                model.is_archived == True, LT(model.date_modified, cutoff_date)
            ).delete_many()
            logger.info(
                "Purge old %s.",
                model.__name__,
                extra={
                    "component": "saq",
                    "task": "purge_db_expired_items",
                    "num_purged": deleted.deleted_count,
                },
            )
        except Exception:
            logger.exception(
                "Failed to purge %s.",
                model.__name__,
                extra={"component": "saq", "task": "purge_db_expired_items"},
            )


async def purge_db_expired_items(_: Context) -> None:
    """Purge expired and archived data across all database models, S3 assets, and chargen sessions."""
    from beanie.odm.operators.find.comparison import LT

    from vapi.db.models import (
        AuditLog,
        ChargenSession,
        S3Asset,
    )
    from vapi.lib.database import init_database

    logger.info(
        "Start database cleanup.", extra={"component": "saq", "task": "purge_db_expired_items"}
    )

    # We need to initialize the database here b/c the tasks are run in a separate process from the main application.
    await init_database()

    await _purge_archived_models()

    cutoff_date = time_now() - timedelta(days=30)

    # Purge audit logs separately because they are not archived
    try:
        deleted = await AuditLog.find(LT(AuditLog.date_modified, cutoff_date)).delete_many()
        logger.info(
            "Purge old AuditLogs.",
            extra={
                "component": "saq",
                "task": "purge_db_expired_items",
                "num_purged": deleted.deleted_count,
            },
        )
    except Exception:
        logger.exception(
            "Failed to purge AuditLogs.",
            extra={"component": "saq", "task": "purge_db_expired_items"},
        )

    try:
        aws_service = AWSS3Service()
        assets = await S3Asset.find(
            S3Asset.is_archived == True, LT(S3Asset.date_modified, cutoff_date)
        ).to_list()
        for asset in assets:
            await aws_service.delete_asset(asset)

        logger.info(
            "Purge old S3Assets.",
            extra={
                "component": "saq",
                "task": "purge_db_expired_items",
                "num_purged": len(assets),
            },
        )
    except Exception:
        logger.exception(
            "Failed to purge S3Assets.",
            extra={"component": "saq", "task": "purge_db_expired_items"},
        )

    # Purge expired chargen sessions and their temporary characters
    try:
        expired_sessions = await ChargenSession.find(
            ChargenSession.expires_at < time_now(), fetch_links=True
        ).to_list()
        for session in expired_sessions:
            for character in session.characters:
                await character.delete()  # type: ignore [attr-defined]
            await session.delete()

        logger.info(
            "Purge expired ChargenSessions.",
            extra={
                "component": "saq",
                "task": "purge_db_expired_items",
                "num_purged": len(expired_sessions),
            },
        )
    except Exception:
        logger.exception(
            "Failed to purge ChargenSessions.",
            extra={"component": "saq", "task": "purge_db_expired_items"},
        )

    logger.info(
        "Database cleanup completed.",
        extra={"component": "saq", "task": "purge_db_expired_items"},
    )
