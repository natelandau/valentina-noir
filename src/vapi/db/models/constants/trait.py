"""Trait model."""

from typing import Annotated, ClassVar

from beanie import (
    Insert,
    PydanticObjectId,
    Replace,
    Save,
    SaveChanges,
    Update,
    before_event,
)
from pydantic import BeforeValidator, Field

from vapi.constants import CharacterClass, GameVersion
from vapi.db.models.base import BaseDocument
from vapi.lib.validation import empty_string_to_none

from .advantage_category import AdvantageCategory
from .sheet_section import CharSheetSection
from .trait_categories import TraitCategory


class Trait(BaseDocument):
    """Trait model."""

    name: Annotated[str, Field(min_length=3, max_length=50)]
    description: Annotated[
        str | None,
        Field(default=None),
        BeforeValidator(empty_string_to_none),
    ] = None
    character_classes: list[CharacterClass] = Field(default_factory=list)
    game_versions: list[GameVersion] = Field(default_factory=list)

    link: Annotated[str | None, Field(default=None)] = None

    show_when_zero: Annotated[bool, Field(default=True)] = True
    max_value: Annotated[int, Field(ge=0, le=100, default=5)] = 5
    min_value: Annotated[int, Field(ge=0, le=100, default=0)] = 0
    is_custom: Annotated[bool, Field(default=False)] = False
    initial_cost: Annotated[int, Field(ge=0, le=100, default=1)] = 1
    upgrade_cost: Annotated[int, Field(ge=0, le=100, default=2)] = 2

    sheet_section_name: str | None = None
    sheet_section_id: PydanticObjectId | None = None

    parent_category_name: str | None = None
    parent_category_id: PydanticObjectId
    custom_for_character_id: Annotated[PydanticObjectId | None, Field(default=None)] = None

    advantage_category_id: PydanticObjectId | None = None
    advantage_category_name: str | None = None

    @before_event(Insert, Replace, Save, Update, SaveChanges)
    async def update_fields(self) -> None:
        """Update the sheet_section_name and parent_category_name fields."""
        parent_category = await TraitCategory.find_one(TraitCategory.id == self.parent_category_id)
        self.parent_category_name = parent_category.name

        sheet_section = await CharSheetSection.find_one(
            CharSheetSection.id == parent_category.parent_sheet_section_id
        )
        self.sheet_section_name = sheet_section.name
        self.sheet_section_id = sheet_section.id

        if self.advantage_category_id:
            advantage_category = await AdvantageCategory.find_one(
                AdvantageCategory.id == self.advantage_category_id
            )
            if self.advantage_category_name != advantage_category.name:
                self.advantage_category_name = advantage_category.name

    class Settings:
        """Settings for the model."""

        indexes: ClassVar[list[str]] = [
            "name",
            "character_classes",
            "game_versions",
            "is_custom",
            "custom_for_character_id",
            "parent_category_id",
        ]
