"""Shared utility for building audit change diffs from patch DTOs.

Compare a msgspec.Struct patch DTO against a target model instance and apply
the non-UNSET fields, returning a dict of ``{"field": {"old": x, "new": y}}``
for every field that actually changed. Handles nested attribute patches via
an optional prefix for dotted keys.
"""

from __future__ import annotations

import msgspec


def build_audit_changes(
    target: object,
    patch: msgspec.Struct,
    *,
    prefix: str = "",
    exclude: frozenset[str] = frozenset(),
) -> dict[str, dict[str, object]]:
    """Apply non-UNSET patch fields to target and return a diff of actual changes.

    Iterates the patch DTO's ``__struct_fields__``, skipping UNSET values,
    excluded fields, and fields not present on the target. For each remaining
    field, captures the old value, sets the new value, and records the diff
    if the value actually changed.

    Args:
        target: The model instance to mutate in-place.
        patch: A msgspec.Struct with UNSET defaults for omitted fields.
        prefix: Optional dotted prefix for change keys (e.g., ``"vampire_attributes."``).
        exclude: Field names to skip entirely.

    Returns:
        Dict mapping changed field names to ``{"old": ..., "new": ...}`` diffs.
        Empty dict if nothing changed.
    """
    changes: dict[str, dict[str, object]] = {}

    for field_name in patch.__struct_fields__:
        if field_name in exclude:
            continue

        value = getattr(patch, field_name)
        if isinstance(value, msgspec.UnsetType):
            continue

        if not hasattr(target, field_name):
            continue

        old = getattr(target, field_name)
        if old != value:
            key = f"{prefix}{field_name}" if prefix else field_name
            changes[key] = {"old": old, "new": value}
            setattr(target, field_name, value)

    return changes
