"""Restore handler.

Reverse one archive action by its batch id. Because every row archived together
shares a batch id (see archive_handlers), restore is a single sweep across every
archivable model, no need to re-walk the entity graph. Rows archived
independently (different batch id) are left untouched.
"""

import logging
from uuid import UUID

from tortoise.models import Model
from tortoise.transactions import in_transaction

from vapi.db.archivable import archivable_models
from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.base import new_uuid
from vapi.db.sql_models.character import Character
from vapi.db.sql_models.notes import Note
from vapi.db.sql_models.user import CampaignExperience
from vapi.utils.time import time_now

from .archive_handlers import ArchiveContext, CharacterArchiveHandler, _archive_where

logger = logging.getLogger("vapi")

# Parents that can be archived on their own after a row joined a batch. A row restored
# under such a parent goes back to that parent's batch.
_NOTE_AND_ASSET_PARENTS: tuple[str, ...] = ("campaign", "book", "chapter", "character")


def _parent_context(parent: Model) -> ArchiveContext:
    """Return an archive context that restores a row together with its archived parent."""
    return ArchiveContext(
        batch_id=parent.archive_batch_id or new_uuid(),  # ty:ignore[unresolved-attribute]
        now=parent.archive_date or time_now(),  # ty:ignore[unresolved-attribute]
    )


async def _rearchive_under_archived_parents(restored_ids: dict[type[Model], list[UUID]]) -> None:
    """Re-archive restored rows whose parent was archived after the batch was created.

    A later parent archive skips rows that are already archived, so those rows keep this
    batch id. Restoring them while the parent stays archived would bring them back inside
    a deleted campaign, book, chapter, or character.
    """
    characters = await Character.filter(
        id__in=restored_ids[Character], is_archived=False, campaign__is_archived=True
    ).prefetch_related("campaign")
    for character in characters:
        await CharacterArchiveHandler(
            character=character, ctx=_parent_context(character.campaign)
        ).handle()

    experiences = await CampaignExperience.filter(
        id__in=restored_ids[CampaignExperience], is_archived=False, campaign__is_archived=True
    ).prefetch_related("campaign")
    for experience in experiences:
        await _archive_where(
            CampaignExperience, _parent_context(experience.campaign), id=experience.id
        )

    for model in (Note, S3Asset):
        for parent_field in _NOTE_AND_ASSET_PARENTS:
            rows = await model.filter(
                id__in=restored_ids[model],
                is_archived=False,
                **{f"{parent_field}__is_archived": True},
            ).prefetch_related(parent_field)
            for row in rows:
                await _archive_where(model, _parent_context(getattr(row, parent_field)), id=row.id)


async def restore_archive_batch(batch_id: UUID) -> int:
    """Reactivate every row stamped with ``batch_id``; return the row count.

    Restore is one logical action, so the whole sweep runs in a single
    transaction: a mid-sweep failure rolls back rather than leaving a batch
    half-restored. Clearing archive_date/archive_batch_id is also enforced by
    the DB trigger when is_archived flips false; setting them here keeps the
    handler correct on its own terms.

    The returned count includes rows that go straight back under a parent that is
    still archived.
    """
    total = 0
    async with in_transaction():
        restored_ids: dict[type[Model], list[UUID]] = {
            model: [row.id for row in await model.filter(archive_batch_id=batch_id).only("id")]
            for model in (Character, CampaignExperience, Note, S3Asset)
        }
        for model in archivable_models():
            total += await model.filter(archive_batch_id=batch_id).update(
                is_archived=False,
                archive_date=None,
                archive_batch_id=None,
            )
        await _rearchive_under_archived_parents(restored_ids)

    logger.debug(
        "Restore archive batch.",
        extra={"component": "restore_handler", "batch_id": str(batch_id), "rows": total},
    )
    return total
