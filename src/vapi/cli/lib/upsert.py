"""Shared upsert-and-count primitives for fixture syncing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vapi.cli.lib.comparison import needs_update

if TYPE_CHECKING:
    from collections.abc import Sequence

    from vapi.cli.lib.sync_counts import SyncCounts
    from vapi.db.sql_models.base import BaseModel

# Rows per INSERT in the cold-start bulk path; large enough to collapse the
# ~800-row traits table into a couple of round trips, small enough to stay well
# under PostgreSQL's parameter limit for wide tables.
SEED_BULK_BATCH_SIZE = 500


async def upsert(
    model: type[BaseModel],
    *,
    lookup: dict[str, Any],
    defaults: dict[str, Any],
    counts: SyncCounts,
) -> Any:
    """Create or update a row by its lookup fields and tally the outcome.

    Centralizes the get-or-create, dirty-check, and create/update counting that
    every fixture syncer needs, so a change to the upsert semantics lives in one
    place instead of being copied across each syncer.

    Args:
        model: The Tortoise model to upsert into.
        lookup: The fields that identify an existing row.
        defaults: The field values to set on create or refresh on update.
        counts: The counter to increment for the create or update.

    Returns:
        The created or updated model instance.
    """
    instance, created = await model.get_or_create(defaults=defaults, **lookup)
    if created:
        counts.created += 1
    elif needs_update(instance, defaults):
        await instance.update_from_dict(defaults).save()
        counts.updated += 1
    return instance


async def bulk_create_new(
    model: type[BaseModel],
    instances: Sequence[BaseModel],
    counts: SyncCounts,
) -> None:
    """Insert freshly built, unsaved instances in one batch and tally them as creates.

    The seed cold-start fast path: on an empty table every fixture row is a create,
    so a single bulk INSERT replaces one get_or_create round trip per row. Callers
    guarantee the table is empty (see the syncers), so no conflict handling is needed.

    bulk_create bypasses BaseModel.save(), so this applies the same string
    normalization save() would and marks each instance saved afterward so downstream
    M2M linking (e.g. clan disciplines) treats the rows as persisted.

    Args:
        model: The Tortoise model to insert into.
        instances: Unsaved instances to insert.
        counts: The counter to increment by the number of rows created.
    """
    if not instances:
        return
    for instance in instances:
        instance.normalize_string_fields()
    await model.bulk_create(instances, batch_size=SEED_BULK_BATCH_SIZE)
    for instance in instances:
        # bulk_create leaves instances flagged unsaved; the rows exist, so mark them
        # persisted for any post-insert M2M/relation work that guards on _saved_in_db.
        instance._saved_in_db = True  # noqa: SLF001
    counts.created += len(instances)
