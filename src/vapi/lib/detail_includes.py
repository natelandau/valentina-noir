"""Helpers for optional child-resource includes on detail endpoints."""

from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum

from tortoise.models import Model
from tortoise.queryset import Prefetch


def active_prefetch(
    relation: str,
    model: type[Model],
    nested: Sequence[str] | None = None,
) -> Prefetch:
    """Build a ``Prefetch`` that filters out soft-deleted (``is_archived=True``) rows.

    Centralizes the archive-filter policy so every detail-include map applies
    the same rule. Optional ``nested`` relation names are chained onto the
    queryset via ``prefetch_related`` to avoid N+1 loads on downstream DTO
    hydration.
    """
    qs = model.filter(is_archived=False)
    if nested:
        qs = qs.prefetch_related(*nested)
    return Prefetch(relation, queryset=qs)


async def apply_includes[E: StrEnum](
    obj: Model,
    include: Iterable[E] | None,
    prefetch_map: Mapping[E, Sequence[str | Prefetch]],
) -> set[E]:
    """Prefetch related rows for requested includes and return the normalized set.

    Handlers that support an optional ``include`` query parameter use this
    helper to dedupe the caller's include list, gather the relation names to
    prefetch from the domain's prefetch map, and hand the normalized set back
    to the response DTO's ``from_model`` so it can embed the right children.

    Plain strings go through ``Model.fetch_related``. ``Prefetch`` objects
    can't - Tortoise only accepts relation-name strings there - so they're
    resolved via a fresh PK-scoped QuerySet and hydrated back onto the
    existing ``obj`` using Tortoise's internal ``_set_result_for_query`` hook
    (there is no public setter for ``ReverseRelation`` / ``ManyToManyRelation``
    containers).
    """
    requested: set[E] = set(include) if include else set()
    string_prefetches: list[str] = []
    prefetch_objects: list[Prefetch] = []
    for inc in requested:
        for item in prefetch_map[inc]:
            if isinstance(item, Prefetch):
                prefetch_objects.append(item)
            else:
                string_prefetches.append(item)

    if string_prefetches:
        await obj.fetch_related(*string_prefetches)

    if prefetch_objects:
        refreshed = await type(obj).filter(pk=obj.pk).prefetch_related(*prefetch_objects).first()
        if refreshed is None:
            msg = (
                f"Failed to reload {type(obj).__name__}(pk={obj.pk!r}) for Prefetch hydration - "
                "row vanished mid-request"
            )
            raise RuntimeError(msg)
        for prefetch in prefetch_objects:
            attr = prefetch.to_attr or prefetch.relation.partition("__")[0]
            refreshed_value = getattr(refreshed, attr)
            container = getattr(obj, attr)
            if hasattr(container, "_set_result_for_query"):
                container._set_result_for_query(  # noqa: SLF001
                    list(refreshed_value), prefetch.to_attr
                )
            else:
                setattr(obj, attr, refreshed_value)

    return requested
