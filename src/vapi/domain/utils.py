"""Domain utilities."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from vapi.db.sql_models.character_sheet import CharacterTrait, Trait
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from uuid import UUID


async def resolve_trait_id_from_mixed_source(trait_id: UUID) -> UUID:
    """Resolve a trait ID from either a trait ID or character trait ID.

    Accept either a trait UUID or a character trait UUID and return
    the corresponding trait UUID. If the input is already a trait ID, return
    the same ID. If it's a character trait ID, return the associated trait ID.

    Args:
        trait_id: The trait or character trait UUID to resolve.

    Returns:
        The resolved trait UUID.

    Raises:
        ValueError: If the ID matches neither a Trait nor a CharacterTrait.
    """
    trait = await Trait.get_or_none(id=trait_id)
    if trait:
        return trait.id

    character_trait = await CharacterTrait.get_or_none(id=trait_id).select_related("trait")
    if character_trait:
        return character_trait.trait.id

    msg = "Invalid trait ID"
    raise ValueError(msg)


async def validate_trait_ids_from_mixed_sources(
    trait_ids: list[UUID],
) -> list[UUID]:
    """Validate a list of trait IDs or character trait IDs and return valid trait IDs.

    Accept a mixed list of trait UUIDs and character trait UUIDs,
    validate each one, and return a list of the corresponding trait UUIDs.
    All IDs are resolved concurrently.

    Args:
        trait_ids: The list of trait or character trait UUIDs to validate.

    Returns:
        The list of validated trait UUIDs.

    Raises:
        ValidationError: If any of the trait IDs are invalid.
    """

    async def _resolve(trait_id: UUID) -> UUID:
        try:
            return await resolve_trait_id_from_mixed_source(trait_id)
        except ValueError as e:
            raise ValidationError(
                detail="Trait not found",
                invalid_parameters=[
                    {"field": "trait_ids", "message": f"Trait {trait_id} not found"},
                ],
            ) from e

    return list(await asyncio.gather(*[_resolve(tid) for tid in trait_ids]))
