"""Tasks for SAQ.

This module contains the tasks for the SAQ plugin which are run at scheduled intervals.  Keep in
mind that the tasks are run in a separate process from the main application.
"""

import logging
from datetime import timedelta

from saq.types import Context

from vapi.utils.time import time_now

logger = logging.getLogger("vapi")


async def purge_db_expired_items(_: Context) -> None:
    """Purge old audit logs."""
    from beanie.odm.operators.find.comparison import LT

    from vapi.db.models import (
        AuditLog,
        Campaign,
        CampaignBook,
        CampaignChapter,
        Character,
        CharacterInventory,
        Company,
        DictionaryTerm,
        Note,
        QuickRoll,
        S3Asset,
        User,
    )
    from vapi.lib.database import init_database

    logger.info(
        "Start database cleanup.", extra={"component": "saq", "task": "purge_db_expired_items"}
    )

    # We need to initialize the database here b/c the tasks are run in a separate process from the main application.
    await init_database()
    cutoff_date = time_now() - timedelta(days=30)

    for model in [
        Character,
        CharacterInventory,
        DictionaryTerm,
        Company,
        Note,
        QuickRoll,
        Campaign,
        CampaignBook,
        CampaignChapter,
        User,
        S3Asset,
    ]:
        deleted = await model.find(
            model.is_archived == True, LT(model.date_modified, cutoff_date)
        ).delete_many()
        msg = f"Purge old {model.__name__}."
        logger.info(
            msg,
            extra={
                "component": "saq",
                "task": "purge_db_expired_items",
                "num_purged": deleted.deleted_count,
            },
        )

    # Purge audit logs separately because they are not archived
    deleted = await AuditLog.find(LT(AuditLog.date_modified, cutoff_date)).delete_many()
    msg = "Purge old AuditLogs."
    logger.info(
        msg,
        extra={
            "component": "saq",
            "task": "purge_db_expired_items",
            "num_purged": deleted.deleted_count,
        },
    )

    logger.info(
        "Database cleanup completed.",
        extra={"component": "saq", "task": "purge_db_expired_items"},
    )
