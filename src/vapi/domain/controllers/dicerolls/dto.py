"""Gameplay DTOs."""

from datetime import datetime
from uuid import UUID

import msgspec

from vapi.constants import DiceSize, RollResultType
from vapi.db.sql_models.diceroll import DiceRoll, DiceRollResult
from vapi.utils.strings import convert_int_to_emoji


class DiceRollCreate(msgspec.Struct):
    """Request body for creating a dice roll."""

    difficulty: int | None = None
    dice_size: DiceSize = DiceSize.D10
    num_dice: int = 1
    num_desperation_dice: int = 0
    comment: str | None = None
    trait_ids: list[UUID] = []
    campaign_id: UUID | None = None
    character_id: UUID | None = None


class QuickRollRequest(msgspec.Struct):
    """Request body for executing a quick roll."""

    quickroll_id: UUID
    character_id: UUID
    comment: str | None = None
    difficulty: int = 6
    num_desperation_dice: int = 0


class DiceRollResultResponse(msgspec.Struct):
    """Response body for a dice roll result."""

    total_result: int | None
    total_result_type: str
    total_result_humanized: str
    total_dice_roll: list[int]
    player_roll: list[int]
    desperation_roll: list[int]
    total_dice_roll_emoji: str
    total_dice_roll_shortcode: str
    player_roll_emoji: str
    player_roll_shortcode: str
    desperation_roll_emoji: str
    desperation_roll_shortcode: str

    @classmethod
    def from_model(cls, m: DiceRollResult) -> "DiceRollResultResponse":
        """Convert a Tortoise DiceRollResult to a response Struct."""
        return cls(
            total_result=m.total_result,
            total_result_type=m.total_result_type.value
            if isinstance(m.total_result_type, RollResultType)
            else m.total_result_type,
            total_result_humanized=m.total_result_humanized,
            total_dice_roll=m.total_dice_roll,
            player_roll=m.player_roll,
            desperation_roll=m.desperation_roll,
            total_dice_roll_emoji=" ".join(
                convert_int_to_emoji(num=d) for d in sorted(m.total_dice_roll)
            ),
            total_dice_roll_shortcode=" ".join(
                convert_int_to_emoji(num=d, as_shortcode=True) for d in sorted(m.total_dice_roll)
            ),
            player_roll_emoji=" ".join(convert_int_to_emoji(num=d) for d in sorted(m.player_roll)),
            player_roll_shortcode=" ".join(
                convert_int_to_emoji(num=d, as_shortcode=True) for d in sorted(m.player_roll)
            ),
            desperation_roll_emoji=" ".join(
                convert_int_to_emoji(num=d) for d in sorted(m.desperation_roll)
            ),
            desperation_roll_shortcode=" ".join(
                convert_int_to_emoji(num=d, as_shortcode=True) for d in sorted(m.desperation_roll)
            ),
        )


class DiceRollResponse(msgspec.Struct):
    """Response body for a dice roll."""

    id: UUID
    date_created: datetime
    date_modified: datetime
    difficulty: int | None
    dice_size: int
    num_dice: int
    num_desperation_dice: int
    result: DiceRollResultResponse | None
    comment: str | None
    trait_ids: list[UUID]
    user_id: UUID | None
    character_id: UUID | None
    campaign_id: UUID | None
    company_id: UUID

    @classmethod
    def from_model(cls, m: DiceRoll) -> "DiceRollResponse":
        """Convert a Tortoise DiceRoll to a response Struct.

        Requires prefetching: roll_result, traits.
        """
        roll_result = getattr(m, "roll_result", None)
        return cls(
            id=m.id,
            date_created=m.date_created,
            date_modified=m.date_modified,
            difficulty=m.difficulty,
            dice_size=m.dice_size,
            num_dice=m.num_dice,
            num_desperation_dice=m.num_desperation_dice,
            result=DiceRollResultResponse.from_model(roll_result) if roll_result else None,
            comment=m.comment,
            trait_ids=[t.id for t in m.traits],
            user_id=m.user_id,  # type: ignore[attr-defined]
            character_id=m.character_id,  # type: ignore[attr-defined]
            campaign_id=m.campaign_id,  # type: ignore[attr-defined]
            company_id=m.company_id,  # type: ignore[attr-defined]
        )
