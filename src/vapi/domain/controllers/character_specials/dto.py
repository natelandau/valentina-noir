"""Hunter and Werewolf specials DTOs."""

from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from vapi.constants import HunterEdgeType


class CharacterPerkDTO(BaseModel):
    """Character perk DTO."""

    id: PydanticObjectId
    name: str
    description: str | None = None


class CharacterEdgeAndPerksDTO(BaseModel):
    """Character edge and perks DTO."""

    id: PydanticObjectId
    name: str
    description: str | None = None
    pool: str | None = None
    system: str | None = None
    type: HunterEdgeType | None = None
    perks: list[CharacterPerkDTO] = Field(default_factory=list)
