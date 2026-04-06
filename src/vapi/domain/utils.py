"""Domain utilities."""

from uuid import UUID

from vapi.db.sql_models.character import CharacterTrait
from vapi.db.sql_models.character_sheet import Trait
from vapi.lib.exceptions import ValidationError


async def validate_trait_ids_from_mixed_sources(
    trait_ids: list[UUID],
) -> list[UUID]:
    """Validate a list of trait IDs or character trait IDs and return valid trait IDs.

    Accept a mixed list of trait UUIDs and character trait UUIDs,
    validate each one, and return a list of the corresponding trait UUIDs.
    Uses two batch queries instead of per-ID lookups.

    Args:
        trait_ids: The list of trait or character trait UUIDs to validate.

    Returns:
        The list of validated trait UUIDs.

    Raises:
        ValidationError: If any of the trait IDs are invalid.
    """
    if not trait_ids:
        return []

    unique_ids = set(trait_ids)

    # Batch 1: check which IDs are direct Trait IDs
    matching_traits = await Trait.filter(id__in=unique_ids)
    resolved: dict[UUID, UUID] = {t.id: t.id for t in matching_traits}

    # Batch 2: resolve remaining IDs as CharacterTrait IDs
    remaining_ids = unique_ids - resolved.keys()
    if remaining_ids:
        character_traits = await CharacterTrait.filter(id__in=remaining_ids).select_related("trait")
        for ct in character_traits:
            resolved[ct.id] = ct.trait.id

    # Check for any unresolved IDs
    unresolved = unique_ids - resolved.keys()
    if unresolved:
        bad_id = next(iter(unresolved))
        raise ValidationError(
            detail="Trait not found",
            invalid_parameters=[
                {"field": "trait_ids", "message": f"Trait {bad_id} not found"},
            ],
        )

    return [resolved[tid] for tid in trait_ids]
