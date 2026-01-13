"""Character concept model."""

from typing import Annotated

from beanie import PydanticObjectId
from pydantic import Field

from vapi.db.models.base import BaseDocument

from .shared import Specialty


class CharacterConcept(BaseDocument):
    """Character concept model.

    Chargen usage:
    When generating a character, the `ability_affinity` and `attribute_affinity` are the trait categories that are boosted by the RNG engine.
    """

    name: str
    description: str
    examples: list[str]

    # Company ID is optional because it is only required for custom character concepts.
    company_id: Annotated[PydanticObjectId | None, Field(examples=["68c1f7152cae3787a09a74fa"])] = (
        None
    )

    # The number of specialties that are available to the character. If this number is smaller that the length of the specialties list, the user must select up to this number of specialties.
    max_specialties: int = Field(default=1)
    specialties: list[Specialty] = Field(default_factory=list)
    favored_ability_names: list[str] = Field(default_factory=list)
