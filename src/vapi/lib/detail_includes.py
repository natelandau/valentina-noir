"""Helpers for optional child-resource includes on detail endpoints."""

from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum

from tortoise.models import Model


async def apply_includes[E: StrEnum](
    obj: Model,
    include: Iterable[E] | None,
    prefetch_map: Mapping[E, Sequence[str]],
) -> set[E]:
    """Prefetch related rows for requested includes and return the normalized set.

    Handlers that support an optional ``include`` query parameter use this
    helper to dedupe the caller's include list, gather the relation names to
    prefetch from the domain's prefetch map, call ``fetch_related`` once, and
    hand the normalized set to the response DTO's ``from_model`` so it can
    embed the right children.
    """
    requested: set[E] = set(include) if include else set()
    prefetches: list[str] = []
    for inc in requested:
        prefetches.extend(prefetch_map[inc])
    if prefetches:
        await obj.fetch_related(*prefetches)
    return requested
