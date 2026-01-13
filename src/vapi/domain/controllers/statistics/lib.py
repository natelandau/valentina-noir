"""Statistics library."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vapi.constants import RollResultType
from vapi.db.models import DiceRoll, Trait

from . import dto

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beanie import PydanticObjectId


async def calculate_roll_statistics(
    filters: Sequence[Any],
    num_top_traits: int = 5,
) -> dto.RollStatistics:
    """Calculate the statistics for a list of dice rolls."""
    dice_rolls_with_traits = await DiceRoll.find(
        *filters, DiceRoll.trait_ids != [], fetch_links=True
    ).to_list()

    # Calculate trait usage counts
    trait_usage_counts: dict[PydanticObjectId, int] = {}
    for dice_roll in dice_rolls_with_traits:
        for trait_id in dice_roll.trait_ids:
            trait_usage_counts[trait_id] = trait_usage_counts.get(trait_id, 0) + 1

    # Get top traits by usage count
    top_trait_ids = sorted(trait_usage_counts.items(), key=lambda x: x[1], reverse=True)[
        :num_top_traits
    ]

    # Fetch trait details for top traits
    top_traits_by_usage: list[dict[str, int | str | PydanticObjectId]] = []
    for trait_id, usage_count in top_trait_ids:
        trait = await Trait.get(trait_id)
        if trait:
            top_traits_by_usage.append(
                {
                    "name": trait.name,
                    "usage_count": usage_count,
                    "trait_id": trait_id,
                }
            )

    return dto.RollStatistics(
        total_rolls=await DiceRoll.find(*filters).count(),
        average_difficulty=await DiceRoll.find(*filters).avg(DiceRoll.difficulty),
        average_pool=await DiceRoll.find(*filters).avg(DiceRoll.num_dice),
        botches=await DiceRoll.find(
            *filters, DiceRoll.result.total_result_type == RollResultType.BOTCH
        ).count(),
        successes=await DiceRoll.find(
            *filters, DiceRoll.result.total_result_type == RollResultType.SUCCESS
        ).count(),
        failures=await DiceRoll.find(
            *filters, DiceRoll.result.total_result_type == RollResultType.FAILURE
        ).count(),
        criticals=await DiceRoll.find(
            *filters, DiceRoll.result.total_result_type == RollResultType.CRITICAL
        ).count(),
        top_traits=top_traits_by_usage,
    )
