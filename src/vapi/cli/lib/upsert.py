"""Shared upsert-and-count primitive for fixture syncing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vapi.cli.lib.comparison import needs_update

if TYPE_CHECKING:
    from tortoise.models import Model

    from vapi.cli.lib.sync_counts import SyncCounts


async def upsert(
    model: type[Model],
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
