"""Statistics library."""

from __future__ import annotations

from typing import Any

from tortoise.expressions import Subquery
from tortoise.functions import Avg, Count

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

    # Count in SQL so the cost tracks the response size, not the stored roll history.
    trait_counts = (
        await Trait.filter(is_archived=False, dice_rolls__id__in=Subquery(base_qs.values("id")))
        .annotate(usage_count=Count("id"))
        .group_by("id", "name")
        .order_by("-usage_count", "name")
        .limit(num_top_traits)
        .values("id", "name", "usage_count")
    )
    top_traits_by_usage: list[dict[str, Any]] = [
        {"name": row["name"], "usage_count": row["usage_count"], "trait_id": row["id"]}
        for row in trait_counts
    ]

    # Calculate aggregate statistics
    total_rolls = await base_qs.count()

    avg_result = await base_qs.annotate(
        avg_difficulty=Avg("difficulty"), avg_pool=Avg("num_dice")
    ).values("avg_difficulty", "avg_pool")
    avg_difficulty = avg_result[0]["avg_difficulty"] if avg_result else None
    avg_pool = avg_result[0]["avg_pool"] if avg_result else None

    outcome_rows = (
        await base_qs.filter(roll_result__total_result_type__isnull=False)
        .annotate(outcome_count=Count("id"))
        .group_by("roll_result__total_result_type")
        .values("roll_result__total_result_type", "outcome_count")
    )
    outcome_counts: dict[str, int] = {
        row["roll_result__total_result_type"]: row["outcome_count"] for row in outcome_rows
    }

    return dto.RollStatistics(
        total_rolls=total_rolls,
        average_difficulty=avg_difficulty,
        average_pool=avg_pool,
        botches=outcome_counts.get(RollResultType.BOTCH, 0),
        successes=outcome_counts.get(RollResultType.SUCCESS, 0),
        failures=outcome_counts.get(RollResultType.FAILURE, 0),
        criticals=outcome_counts.get(RollResultType.CRITICAL, 0),
        top_traits=top_traits_by_usage,
    )
