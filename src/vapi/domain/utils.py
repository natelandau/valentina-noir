"""Domain utilities."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from beanie import Document
from litestar.dto import DTOData  # noqa: TC002

from vapi.db.sql_models.character import CharacterTrait
from vapi.db.sql_models.character_sheet import Trait
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


# ---------------------------------------------------------------------------
# Beanie/Pydantic helpers (still used by unmigrated domains)
# ---------------------------------------------------------------------------


def patch_document_from_dict[T: Document](document: T, data: dict[str, Any]) -> T:
    """Patch a Beanie document from a dictionary, recursing into nested dicts.

    Args:
        document: The document to update.
        data: The data to update the document with.

    Returns:
        The updated document.
    """

    def _apply(target: Any, patch: dict[str, Any]) -> None:
        computed = target.model_computed_fields
        for key, value in patch.items():
            if key in computed:
                continue
            if key in target.model_dump():
                if isinstance(value, dict):
                    _apply(getattr(target, key), value)
                else:
                    setattr(target, key, value)

    _apply(document, data)
    return document


async def patch_dto_data_internal_objects[T: Document](
    original: T, data: DTOData[T]
) -> tuple[T, DTOData]:
    """Update internal objects within a database document with updated data from a DTO.

    Needed because of a bug in how Litestar handles nested objects with PydanticDTOs.
    The default behavior overwrites the entire nested object, deleting values not in
    the new data -- effectively breaking patch operations.

    Args:
        original: The original database document to update.
        data: The data to update the document with.

    Returns:
        A tuple containing the updated document and the data.
    """
    from vapi.db.models.character import HunterAttributes

    internal_object_keys = []
    for key, value in data._data_as_builtins.items():  # noqa: SLF001
        if isinstance(value, dict):
            internal_object_keys.append(key)

            for sub_key, sub_value in value.items():
                internal_object = getattr(original, key)
                setattr(internal_object, sub_key, sub_value)

        if isinstance(value, HunterAttributes):
            if original.hunter_attributes is None:
                continue
            original.hunter_attributes.creed = value.creed
            internal_object_keys.append(key)

    for key in internal_object_keys:
        del data._data_as_builtins[key]  # noqa: SLF001

    await original.save()

    return original, data
