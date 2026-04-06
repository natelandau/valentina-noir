"""Statistics library."""

from __future__ import annotations

from typing import Any

from tortoise.functions import Avg

from vapi.constants import RollResultType
from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.diceroll import DiceRoll

from . import dto


async def calculate_roll_statistics(
    filters: dict[str, Any],
    num_top_traits: int = 5,
) -> dto.RollStatistics:
    """Calculate statistics for a set of dice rolls matching the given filters."""
    base_qs = DiceRoll.filter(**filters)

    # Get dice rolls with prefetched traits for frequency analysis
    dice_rolls_with_traits = [dr for dr in await base_qs.prefetch_related("traits") if dr.traits]

    # Calculate trait usage counts
    trait_usage_counts: dict[Any, int] = {}
    for dice_roll in dice_rolls_with_traits:
        for trait in dice_roll.traits:
            trait_usage_counts[trait.id] = trait_usage_counts.get(trait.id, 0) + 1

    # Get top traits by usage count
    top_trait_entries = sorted(trait_usage_counts.items(), key=lambda x: x[1], reverse=True)[
        :num_top_traits
    ]

    # Batch fetch trait details
    top_traits_by_usage: list[dict[str, Any]] = []
    if top_trait_entries:
        top_trait_ids = [tid for tid, _ in top_trait_entries]
        traits_by_id = {t.id: t for t in await Trait.filter(id__in=top_trait_ids)}
        for trait_id, usage_count in top_trait_entries:
            trait = traits_by_id.get(trait_id)
            if trait:
                top_traits_by_usage.append(
                    {
                        "name": trait.name,
                        "usage_count": usage_count,
                        "trait_id": trait_id,
                    }
                )

    # Calculate aggregate statistics
    total_rolls = await base_qs.count()

    avg_result = await base_qs.annotate(
        avg_difficulty=Avg("difficulty"), avg_pool=Avg("num_dice")
    ).values("avg_difficulty", "avg_pool")
    avg_difficulty = avg_result[0]["avg_difficulty"] if avg_result else None
    avg_pool = avg_result[0]["avg_pool"] if avg_result else None

    return dto.RollStatistics(
        total_rolls=total_rolls,
        average_difficulty=avg_difficulty,
        average_pool=avg_pool,
        botches=await base_qs.filter(roll_result__total_result_type=RollResultType.BOTCH).count(),
        successes=await base_qs.filter(
            roll_result__total_result_type=RollResultType.SUCCESS
        ).count(),
        failures=await base_qs.filter(
            roll_result__total_result_type=RollResultType.FAILURE
        ).count(),
        criticals=await base_qs.filter(
            roll_result__total_result_type=RollResultType.CRITICAL
        ).count(),
        top_traits=top_traits_by_usage,
    )
