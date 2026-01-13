"""Gameplay services."""

from __future__ import annotations

from dataclasses import dataclass

import inflect

from vapi.constants import DiceSize, RollResultType
from vapi.db.models.diceroll import DiceRollResultSchema
from vapi.utils.math import random_num

p = inflect.engine()

__all__ = ("roll_dice",)


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
        result (int): The result of the dice roll.
        dice_size (DiceSize): The size of the dice rolled.
        num_dice (int): The number of dice rolled.

    Returns:
        tuple[RollResultType, str]: The result type and description of the roll.
    """
    if dice_size != DiceSize.D10:
        return RollResultType.OTHER, ""
    if result < 0:
        return RollResultType.BOTCH, f"{result} {p.plural_noun('Success', result)}"
    if result == 0:
        return (
            RollResultType.FAILURE,
            f"{result} {p.plural_noun('Success', result)}",
        )
    if result > num_dice:
        return RollResultType.CRITICAL, f"{result} {p.plural_noun('Success', result)}"
    return RollResultType.SUCCESS, f"{result} {p.plural_noun('Success', result)}"


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
    # Generate rolls
    player_roll = [random_num(dice_size.value) for _ in range(num_dice)]
    desperation_roll = [random_num(dice_size.value) for _ in range(num_desperation_dice)]

    if difficulty is not None:
        # Count results
        player_counts = _count_dice_results(player_roll, difficulty, dice_size.value)
        desperation_counts = _count_dice_results(desperation_roll, difficulty, dice_size.value)

        # Calculate totals
        total_botches = player_counts.botches + desperation_counts.botches
        total_failures = player_counts.failures + desperation_counts.failures
        total_successes = player_counts.successes + desperation_counts.successes
        total_criticals = player_counts.criticals + desperation_counts.criticals

    # Calculate final result based on dice type
    if dice_size == DiceSize.D10 and difficulty is not None:
        effective_botches = max(0, total_botches - total_criticals)
        effective_criticals = max(0, total_criticals - total_botches)
        total_result = total_successes + (effective_criticals * 2) - effective_botches
    else:
        total_result = (
            None if difficulty is None else total_successes - total_failures - total_botches
        )

    if total_result is None:
        result_type, result_humanized = RollResultType.OTHER, ""
    else:
        result_type, result_humanized = _calculate_result_type(
            result=total_result,
            dice_size=dice_size,
            num_dice=num_dice + num_desperation_dice,
        )

    # Pre-sort rolls once
    sorted_player = sorted(player_roll)
    sorted_desperation = sorted(desperation_roll)
    sorted_total = sorted(player_roll + desperation_roll)

    return DiceRollResultSchema(
        total_result=total_result,
        total_result_type=result_type,
        total_result_humanized=result_humanized,
        total_dice_roll=sorted_total,
        player_roll=sorted_player,
        desperation_roll=sorted_desperation,
    )
