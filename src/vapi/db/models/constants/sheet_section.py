"""Character sheet model."""

from typing import ClassVar

from pydantic import Field

from vapi.constants import CharacterClass, GameVersion
from vapi.db.models.base import BaseDocument


class CharSheetSection(BaseDocument):
    """Trait section model."""

    name: str
    description: str | None = None
    character_classes: list[CharacterClass] = Field(default_factory=list)
    game_versions: list[GameVersion] = Field(default_factory=list)
    show_when_empty: bool = Field(default=False)
    order: int = Field(default=0)

    class Settings:
        """Settings for the model."""

        indexes: ClassVar[list[str]] = [
            "name",
            "character_classes",
            "game_versions",
        ]
