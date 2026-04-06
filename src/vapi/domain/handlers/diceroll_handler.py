"""Dice roll handler."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha512

from pydantic import BaseModel, computed_field

from vapi.constants import DiceSize, RollResultType
from vapi.utils.math import random_num
from vapi.utils.strings import convert_int_to_emoji


class HashedBaseModel(BaseModel):
    """Add a __hash__ method to Pydantic models without requiring the frozen=True flag.

    Allow nested objects within database documents to work correctly with
    Litestar's PydanticDTO patch operations.
    """

    def __hash__(self) -> int:
        """Hash the model."""
        return int.from_bytes(
            sha512(
                f"{self.__class__.__qualname__}::{self.model_dump(mode='json')}".encode(
                    "utf-8", errors="ignore"
                )
            ).digest()
        )


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


@dataclass
class DiceCounts:
    """Counts for different dice result types."""

    botches: int = 0
    failures: int = 0
    successes: int = 0
    criticals: int = 0


def _calculate_result_type(
    result: int, dice_size: DiceSize, num_dice: int
) -> tuple[RollResultType, str]:
    """Calculate the result type of the roll.

    Args:
        result: The result of the dice roll.
        dice_size: The size of the dice rolled.
        num_dice: The number of dice rolled.

    Returns:
        tuple[RollResultType, str]: The result type and description of the roll.
    """
    if dice_size != DiceSize.D10:
        return RollResultType.OTHER, ""

    if result < 0:
        result_type = RollResultType.BOTCH
    elif result == 0:
        result_type = RollResultType.FAILURE
    elif result > num_dice:
        result_type = RollResultType.CRITICAL
    else:
        result_type = RollResultType.SUCCESS

    humanized = f"{result} {'Success' if result == 1 else 'Successes'}"
    return result_type, humanized


def _count_dice_results(roll: list[int], difficulty: int, dice_max: int) -> DiceCounts:
    """Count all dice result types in a single pass."""
    counts = DiceCounts()

    for die in roll:
        if die == 1:
            counts.botches += 1
        elif 2 <= die <= difficulty - 1:  # noqa: PLR2004
            counts.failures += 1
        elif difficulty <= die <= dice_max - 1:
            counts.successes += 1
        elif die == dice_max:
            counts.criticals += 1

    return counts


def roll_dice(
    *, num_dice: int, num_desperation_dice: int, difficulty: int | None, dice_size: DiceSize
) -> DiceRollResultSchema:
    """Roll the dice and return the results."""
    player_roll = [random_num(dice_size.value) for _ in range(num_dice)]
    desperation_roll = [random_num(dice_size.value) for _ in range(num_desperation_dice)]

    total_result: int | None = None
    if difficulty is not None:
        player_counts = _count_dice_results(player_roll, difficulty, dice_size.value)
        desperation_counts = _count_dice_results(desperation_roll, difficulty, dice_size.value)

        total_botches = player_counts.botches + desperation_counts.botches
        total_failures = player_counts.failures + desperation_counts.failures
        total_successes = player_counts.successes + desperation_counts.successes
        total_criticals = player_counts.criticals + desperation_counts.criticals

        if dice_size == DiceSize.D10:
            effective_botches = max(0, total_botches - total_criticals)
            effective_criticals = max(0, total_criticals - total_botches)
            total_result = total_successes + (effective_criticals * 2) - effective_botches
        else:
            total_result = total_successes - total_failures - total_botches

    if total_result is None:
        result_type, result_humanized = RollResultType.OTHER, ""
    else:
        result_type, result_humanized = _calculate_result_type(
            result=total_result,
            dice_size=dice_size,
            num_dice=num_dice + num_desperation_dice,
        )

    return DiceRollResultSchema(
        total_result=total_result,
        total_result_type=result_type,
        total_result_humanized=result_humanized,
        total_dice_roll=sorted(player_roll + desperation_roll),
        player_roll=sorted(player_roll),
        desperation_roll=sorted(desperation_roll),
    )
