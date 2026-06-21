"""User quick roll service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vapi.db.sql_models.character_sheet import Trait
from vapi.lib.exceptions import ValidationError

from .validation_svc import validate_trait_ids_from_mixed_sources

if TYPE_CHECKING:
    from uuid import UUID


class UserQuickRollService:
    """Quick roll service."""

    async def validate_quickroll_traits(self, trait_ids: list[UUID]) -> list[Trait]:
        """Validate trait IDs and return the Trait objects for M2M assignment.

        Args:
            trait_ids: The list of trait UUIDs to validate.

        Returns:
            The list of validated Trait objects.

        Raises:
            ValidationError: If no traits remain after validation or any ID is invalid.
        """
        validated_ids = await validate_trait_ids_from_mixed_sources(trait_ids)

        if not validated_ids:
            raise ValidationError(
                detail="Quick roll must have at least one trait",
                invalid_parameters=[
                    {
                        "field": "trait_ids",
                        "message": "Quick roll must have at least one trait",
                    },
                ],
            )

        return await Trait.filter(id__in=validated_ids)
