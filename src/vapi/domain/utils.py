"""Domain utilities."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from beanie import Document
from litestar.dto import DTOData  # noqa: TC002

from vapi.db.models import CharacterTrait, Trait
from vapi.db.models.character import HunterAttributes
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from beanie import PydanticObjectId


async def resolve_trait_id_from_mixed_source(trait_id: PydanticObjectId) -> PydanticObjectId:
    """Resolve a trait ID from either a trait ID or character trait ID.

    This function accepts either a trait ID or a character trait ID and returns
    the corresponding trait ID. If the input is already a trait ID, it returns
    the same ID. If it's a character trait ID, it returns the associated trait ID.

    Args:
        trait_id: The trait ID or character trait ID to resolve.

    Returns:
        The resolved trait ID.

    Raises:
        ValueError: If the trait ID is invalid.
    """
    trait = await Trait.get(trait_id)
    if trait:
        return trait.id
    character_trait = await CharacterTrait.get(trait_id, fetch_links=True)
    if character_trait:
        return character_trait.trait.id  # type: ignore [attr-defined]

    msg = "Invalid trait ID"
    raise ValueError(msg)


async def validate_trait_ids_from_mixed_sources(
    trait_ids: list[PydanticObjectId],
) -> list[PydanticObjectId]:
    """Validate a list of trait IDs or character trait IDs and return a list of valid trait IDs.

    This function accepts a mixed list of trait IDs and character trait IDs,
    validates each one, and returns a list of the corresponding trait IDs.
    All IDs are resolved concurrently.

    Args:
        trait_ids: The list of trait IDs or character trait IDs to validate.

    Returns:
        The list of validated trait IDs.

    Raises:
        ValidationError: If any of the trait IDs are invalid.
    """

    async def _resolve(trait_id: PydanticObjectId) -> PydanticObjectId:
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
    """Update the internal objects within a database document with updated data from a DTO.

    We need this utility because of a bug in the way litestar handles nested objects with PydanticDTOs.  The default behavior overwrites the entire nested object with the new values and will delete any values that are not in the new data - effectively rendering patch operations useless.

    Args:
        original: The original database document to update.
        data: The data to update the document with.

    Returns:
        A tuple containing the updated document and the data.
    """
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
