"""Custom Litestar type decoders and encoders."""

from typing import Any

from beanie import PydanticObjectId


class DecodePydanticObjectId:
    """Create a decoder hook for PydanticObjectId to allow for type conversion in routes."""

    @classmethod
    def is_pydantic_object_id(cls, type: type) -> bool:  # noqa: A002
        """Predicate to check if a type is a PydanticObjectId.

        Args:
            type: The type to check.

        Returns:
            True if the type is a PydanticObjectId, False otherwise.
        """
        return type is PydanticObjectId

    @classmethod
    def decode(cls, type: type, obj: Any) -> Any:  # noqa: A002
        """General decoder hook for unknown types.

        If the type is a PydanticObjectId, decode it.
        Otherwise, raise a NotImplementedError.

        Args:
            type: The type to decode.
            obj: The object to decode.

        Returns:
            The decoded object.

        Raises:
            ValueError: If the object is not a PydanticObjectId.
            NotImplementedError: If the type is not a PydanticObjectId.
        """
        if cls.is_pydantic_object_id(type):
            try:
                return PydanticObjectId(obj)
            except Exception as e:
                raise ValueError(e) from e

        msg = f"Encountered unknown type during decoding: {type!s}"
        raise NotImplementedError(msg)
