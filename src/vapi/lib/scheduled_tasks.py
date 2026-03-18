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

_LOG_EXTRA = {"component": "saq", "task": "purge_db_expired_items"}


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
                extra={**_LOG_EXTRA, "num_purged": deleted.deleted_count},
            )
        except Exception:
            logger.exception(
                "Failed to purge %s.",
                model.__name__,
                extra=_LOG_EXTRA,
            )


async def _purge_audit_logs() -> None:
    """Purge audit log entries older than 30 days."""
    from beanie.odm.operators.find.comparison import LT

    from vapi.db.models import AuditLog

    cutoff_date = time_now() - timedelta(days=30)

    try:
        deleted = await AuditLog.find(LT(AuditLog.date_modified, cutoff_date)).delete_many()
        logger.info(
            "Purge old AuditLogs.",
            extra={**_LOG_EXTRA, "num_purged": deleted.deleted_count},
        )
    except Exception:
        logger.exception(
            "Failed to purge AuditLogs.",
            extra=_LOG_EXTRA,
        )


async def _purge_s3_assets() -> None:
    """Purge archived S3 assets older than 30 days."""
    from beanie.odm.operators.find.comparison import LT

    from vapi.db.models import S3Asset

    cutoff_date = time_now() - timedelta(days=30)

    try:
        assets = await S3Asset.find(
            S3Asset.is_archived == True, LT(S3Asset.date_modified, cutoff_date)
        ).to_list()

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
        logger.exception(
            "Failed to purge S3Assets.",
            extra=_LOG_EXTRA,
        )


async def _purge_chargen_sessions() -> None:
    """Purge expired chargen sessions and their linked characters."""
    from vapi.db.models import ChargenSession

    try:
        expired_sessions = await ChargenSession.find(
            ChargenSession.expires_at < time_now(), fetch_links=True
        ).to_list()
        for session in expired_sessions:
            for character in session.characters:
                try:
                    await character.delete()  # type: ignore [attr-defined]
                except Exception:
                    logger.exception(
                        "Failed to delete character %s from session %s.",
                        getattr(character, "id", "unknown"),
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
    from beanie.odm.operators.find.comparison import LT

    from vapi.db.models import Character

    cutoff_date = time_now() - timedelta(hours=24)

    try:
        characters = await Character.find(
            Character.is_chargen == False,
            Character.is_temporary == True,
            LT(Character.date_modified, cutoff_date),
        ).to_list()
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


async def _purge_orphaned_character_traits() -> None:
    """Purge CharacterTrait documents whose parent Character no longer exists.

    Act as a safety net for any deletion path that bypasses the Character
    @before_event(Delete) hook (e.g., delete_many, manual DB operations).
    """
    from beanie import PydanticObjectId
    from beanie.operators import In

    from vapi.db.models import Character
    from vapi.db.models.character import CharacterTrait

    try:
        # Collect all distinct character_ids referenced by CharacterTrait documents
        pipeline_result = await CharacterTrait.aggregate(
            [{"$group": {"_id": "$character_id"}}]
        ).to_list()
        trait_character_ids = [PydanticObjectId(doc["_id"]) for doc in pipeline_result]

        if not trait_character_ids:
            logger.info(
                "Purge orphaned CharacterTraits.",
                extra={**_LOG_EXTRA, "num_purged": 0},
            )
            return

        # Find which of those character_ids still exist (project only _id to avoid fetching full docs)
        existing_docs = (
            await Character.find(In(Character.id, trait_character_ids))
            .aggregate([{"$project": {"_id": 1}}])
            .to_list()
        )
        existing_ids = {PydanticObjectId(doc["_id"]) for doc in existing_docs}

        # Compute orphaned IDs
        orphaned_ids = [cid for cid in trait_character_ids if cid not in existing_ids]

        if orphaned_ids:
            deleted = await CharacterTrait.find(
                In(CharacterTrait.character_id, orphaned_ids)
            ).delete_many()
            purged_count = deleted.deleted_count
        else:
            purged_count = 0

        logger.info(
            "Purge orphaned CharacterTraits.",
            extra={**_LOG_EXTRA, "num_purged": purged_count},
        )
    except Exception:
        logger.exception(
            "Failed to purge orphaned CharacterTraits.",
            extra=_LOG_EXTRA,
        )


async def purge_db_expired_items(_: Context) -> None:
    """Purge expired and archived data across all database models, S3 assets, and sessions.

    Delegate to focused helper functions for each cleanup concern. Each helper
    handles its own imports, error handling, and logging so that a failure in one
    does not prevent the others from running.
    """
    from vapi.lib.database import init_database

    logger.info("Start database cleanup.", extra=_LOG_EXTRA)

    await init_database()

    await _purge_archived_models()
    await _purge_audit_logs()
    await _purge_s3_assets()
    await _purge_chargen_sessions()
    await _purge_temporary_characters()
    await _purge_orphaned_character_traits()

    logger.info(
        "Database cleanup completed.",
        extra=_LOG_EXTRA,
    )
