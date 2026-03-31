"""Dice roll handler."""

from __future__ import annotations

from dataclasses import dataclass

from vapi.constants import DiceSize, RollResultType
from vapi.db.models.diceroll import DiceRollResultSchema
from vapi.utils.math import random_num


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
