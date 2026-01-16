"""Domain utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from beanie import Document
from litestar.dto import DTOData  # noqa: TC002

from vapi.db.models import CharacterTrait, Trait
from vapi.db.models.character import HunterAttributes
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from beanie import PydanticObjectId

T = TypeVar("T", bound=Document)


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

    Args:
        trait_ids: The list of trait IDs or character trait IDs to validate.

    Returns:
        The list of validated trait IDs.

    Raises:
        ValidationError: If any of the trait IDs are invalid.
    """
    valid_trait_ids = []
    for trait_id in trait_ids:
        try:
            valid_trait_id = await resolve_trait_id_from_mixed_source(trait_id)
        except ValueError as e:
            raise ValidationError(
                detail="Trait not found",
                invalid_parameters=[
                    {"field": "trait_ids", "message": f"Trait {trait_id} not found"},
                ],
            ) from e

        valid_trait_ids.append(valid_trait_id)

    return valid_trait_ids


def patch_document_from_dict[T: Document](document: T, data: dict[str, Any]) -> T:
    """Patch a Beanie document from a dictionary.

    Args:
        document: The document to update.
        data: The data to update the document with.

    Returns:
        The updated document.
    """

    def _patch_internal_dict(original: T, data: dict[str, Any]) -> None:
        for key, value in data.items():
            if key in original.model_dump():
                if isinstance(value, dict):
                    _patch_internal_dict(getattr(original, key), value)
                else:
                    setattr(original, key, value)

    for key, value in data.items():
        if key in document.model_dump():
            if isinstance(value, dict):
                _patch_internal_dict(getattr(document, key), value)
            else:
                setattr(document, key, value)

    return document


async def patch_dto_data_internal_objects(original: T, data: DTOData[T]) -> tuple[T, DTOData]:
    """Update the internal objects within a database document with updated data from a DTO.

    We need this utility because of a bug in the way litestar handles nested objects with PydanticDTOs.  The default behavior overwrites the entire nested object with the new values and will delete any values that are not in the new data - effectively rendering patch operations useless.

    Args:
        original: The original database document to update.
        data: The data to update the document with.

    Returns:
        A tuple containing the updated document and the data.
    """
    # Identify internal nested objects
    internal_object_keys = []
    for key, value in data._data_as_builtins.items():  # noqa: SLF001
        if isinstance(value, dict):
            internal_object_keys.append(key)

            # Now we need to update the original object with the new values
            for sub_key, sub_value in value.items():
                internal_object = getattr(original, key)
                setattr(internal_object, sub_key, sub_value)

        if isinstance(value, HunterAttributes):
            if original.hunter_attributes is None:
                continue
            original.hunter_attributes.creed = value.creed
            internal_object_keys.append(key)

    # Remove the internal object keys from the data
    for key in internal_object_keys:
        del data._data_as_builtins[key]  # noqa: SLF001

    await original.save()

    return original, data
