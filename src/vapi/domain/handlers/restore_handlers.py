"""Restore handler.

Reverse one archive action by its batch id. Because every row archived together
shares a batch id (see archive_handlers), restore is a single sweep across every
archivable model, no need to re-walk the entity graph. Rows archived
independently (different batch id) are left untouched.
"""

import logging
from uuid import UUID

from tortoise.transactions import in_transaction

from vapi.db.archivable import archivable_models

logger = logging.getLogger("vapi")


async def restore_archive_batch(batch_id: UUID) -> int:
    """Reactivate every row stamped with ``batch_id``; return the row count.

    Restore is one logical action, so the whole sweep runs in a single
    transaction: a mid-sweep failure rolls back rather than leaving a batch
    half-restored. Clearing archive_date/archive_batch_id is also enforced by
    the DB trigger when is_archived flips false; setting them here keeps the
    handler correct on its own terms.
    """
    total = 0
    async with in_transaction():
        for model in archivable_models():
            total += await model.filter(archive_batch_id=batch_id).update(
                is_archived=False,
                archive_date=None,
                archive_batch_id=None,
            )

    logger.debug(
        "Restore archive batch.",
        extra={"component": "restore_handler", "batch_id": str(batch_id), "rows": total},
    )
    return total
