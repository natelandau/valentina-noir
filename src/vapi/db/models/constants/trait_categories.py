"""Trait category model."""

from typing import ClassVar

from beanie import PydanticObjectId
from pydantic import Field

from vapi.constants import CharacterClass, GameVersion
from vapi.db.models.base import BaseDocument


class TraitCategory(BaseDocument):
    """Trait category model."""

    name: str
    description: str | None = None
    character_classes: list[CharacterClass] = Field(default_factory=list)
    game_versions: list[GameVersion] = Field(default_factory=list)
    show_when_empty: bool = Field(default=False)
    order: int = Field(default=0)
    parent_sheet_section_id: PydanticObjectId

    initial_cost: int = Field(default=1)
    upgrade_cost: int = Field(default=2)

    class Settings:
        """Settings for the model."""

        indexes: ClassVar[list[str]] = [
            "name",
            "character_classes",
            "parent_sheet_section_id",
            "game_versions",
        ]
