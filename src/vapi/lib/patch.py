"""Apply a msgspec.Struct patch DTO to a model instance.

Mutates the target in-place and returns a shallow diff of the fields that
actually changed. Only non-UNSET fields on the patch are considered; fields
the target doesn't have are silently skipped.
"""

from __future__ import annotations

import msgspec


def apply_patch(
    target: object,
    patch: msgspec.Struct,
    *,
    prefix: str = "",
    exclude: frozenset[str] = frozenset(),
) -> dict[str, dict[str, object]]:
    """Apply a patch DTO to a target model and return a diff of what changed.

    Iterate the patch's fields, skip any that are UNSET (not sent in the
    request), excluded, or absent on the target. For each remaining field,
    compare old vs new — if different, mutate the target via ``setattr`` and
    record the change.

    Only compares at one level of depth. If a field value is a dict and a key
    inside it changed, the entire old and new dicts are recorded — individual
    keys within the dict are not diffed.

    Args:
        target: The model instance to mutate in-place.
        patch: A msgspec.Struct whose fields default to ``msgspec.UNSET``
            for any value not provided by the caller.
        prefix: Prepended to each key in the returned diff dict. Use dotted
            prefixes (e.g., ``"settings."``) when applying patches to nested
            models so the diff keys distinguish them from top-level fields.
        exclude: Field names on the patch to skip entirely. Use this for
            fields that need special handling (e.g., nested relations,
            fields requiring validation before assignment).

    Returns:
        Dict mapping field names to ``{"old": <previous>, "new": <current>}``
        for every field that was actually changed. Empty dict when nothing
        changed or the patch contained only UNSET / same-value fields.

    Example::

        from vapi.lib.patch import apply_patch

        changes = apply_patch(campaign, data)
        request.state.audit_changes = changes
        await campaign.save()
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
