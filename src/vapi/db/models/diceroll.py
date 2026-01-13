"""Diceroll model."""

from typing import ClassVar

from beanie import PydanticObjectId
from pydantic import Field, computed_field

from vapi.constants import (
    DiceSize,
    RollResultType,
)
from vapi.db.models.base import BaseDocument, HashedBaseModel
from vapi.utils.strings import convert_int_to_emoji


class DiceRollResultSchema(HashedBaseModel):
    """Represent the result of a dice roll."""

    total_result: int | None = None
    total_result_type: RollResultType
    total_result_humanized: str
    total_dice_roll: list[int]
    player_roll: list[int]
    desperation_roll: list[int]

    @computed_field  # type: ignore [prop-decorator]
    @property
    def total_dice_roll_emoji(self) -> str:
        """Get the result of the dice roll."""
        return " ".join(convert_int_to_emoji(num=d) for d in sorted(self.total_dice_roll))

    @computed_field  # type: ignore [prop-decorator]
    @property
    def total_dice_roll_shortcode(self) -> str:
        """Get the result of the dice roll."""
        return " ".join(
            convert_int_to_emoji(num=d, as_shortcode=True) for d in sorted(self.total_dice_roll)
        )

    @computed_field  # type: ignore [prop-decorator]
    @property
    def player_roll_emoji(self) -> str:
        """Get the result of the dice roll."""
        return " ".join(convert_int_to_emoji(num=d) for d in sorted(self.player_roll))

    @computed_field  # type: ignore [prop-decorator]
    @property
    def player_roll_shortcode(self) -> str:
        """Get the result of the dice roll."""
        return " ".join(
            convert_int_to_emoji(num=d, as_shortcode=True) for d in sorted(self.player_roll)
        )

    @computed_field  # type: ignore [prop-decorator]
    @property
    def desperation_roll_emoji(self) -> str:
        """Get the result of the dice roll."""
        return " ".join(convert_int_to_emoji(num=d) for d in sorted(self.desperation_roll))

    @computed_field  # type: ignore [prop-decorator]
    @property
    def desperation_roll_shortcode(self) -> str:
        """Get the result of the dice roll."""
        return " ".join(
            convert_int_to_emoji(num=d, as_shortcode=True) for d in sorted(self.desperation_roll)
        )


class DiceRoll(BaseDocument):
    """Dice roll model."""

    difficulty: int | None = None
    dice_size: DiceSize
    num_dice: int
    num_desperation_dice: int = 0
    result: DiceRollResultSchema | None = None
    comment: str | None = None

    trait_ids: list[PydanticObjectId] = Field(default_factory=list)
    user_id: PydanticObjectId | None = None
    character_id: PydanticObjectId | None = None
    campaign_id: PydanticObjectId | None = None
    company_id: PydanticObjectId

    class Settings:
        """Settings for the DiceRoll model."""

        indexes: ClassVar[list[str]] = ["character_id", "campaign_id", "user_id"]
