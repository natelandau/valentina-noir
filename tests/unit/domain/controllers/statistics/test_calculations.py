"""Unit tests for dice roll statistics calculations."""

from typing import Any

import pytest

from vapi.constants import DiceSize, RollResultType
from vapi.domain.controllers.statistics.calculations import calculate_roll_statistics

pytestmark = pytest.mark.anyio


async def test_top_traits_counts_only_matching_rolls_and_active_traits(
    company_factory: Any,
    user_factory: Any,
    trait_factory: Any,
    diceroll_factory: Any,
) -> None:
    """Verify top traits count only rolls matching the filters and skip archived traits."""
    # Given a company with rolls from two users using a mix of traits
    company = await company_factory()
    roller = await user_factory(company=company)
    other = await user_factory(company=company)
    strength = await trait_factory(name="Stats Strength")
    brawl = await trait_factory(name="Stats Brawl")
    archived = await trait_factory(name="Stats Archived", is_archived=True)
    await diceroll_factory(company=company, user=roller, traits=[strength, brawl, archived])
    await diceroll_factory(company=company, user=roller, traits=[strength])
    await diceroll_factory(company=company, user=roller)
    await diceroll_factory(company=company, user=other, traits=[brawl, brawl])
    await diceroll_factory(company=company, user=roller, traits=[brawl], is_archived=True)

    # When calculating statistics for the first user
    stats = await calculate_roll_statistics(
        {"user_id": roller.id, "is_archived": False, "dice_size": DiceSize.D10},
        num_top_traits=5,
    )

    # Then usage counts reflect only that user's active rolls, without the archived trait
    assert stats.total_rolls == 3
    assert [(t["name"], t["usage_count"]) for t in stats.top_traits] == [
        ("Stats Strength", 2),
        ("Stats Brawl", 1),
    ]


async def test_top_traits_respects_limit(
    company_factory: Any,
    user_factory: Any,
    trait_factory: Any,
    diceroll_factory: Any,
) -> None:
    """Verify num_top_traits limits the traits returned to the most used."""
    # Given a user whose rolls use one trait more than another
    company = await company_factory()
    roller = await user_factory(company=company)
    strength = await trait_factory(name="Stats Strength")
    brawl = await trait_factory(name="Stats Brawl")
    await diceroll_factory(company=company, user=roller, traits=[strength, brawl])
    await diceroll_factory(company=company, user=roller, traits=[strength])

    # When asking for only the top trait
    stats = await calculate_roll_statistics(
        {"user_id": roller.id, "is_archived": False, "dice_size": DiceSize.D10},
        num_top_traits=1,
    )

    # Then only the most-used trait is returned
    assert [t["name"] for t in stats.top_traits] == ["Stats Strength"]


async def test_outcome_counts_group_matching_rolls_by_result_type(
    company_factory: Any,
    user_factory: Any,
    diceroll_factory: Any,
) -> None:
    """Verify outcome counts tally each result type over the matching rolls only."""
    # Given a user's rolls covering every outcome, plus rolls that do not match the filters
    company = await company_factory()
    roller = await user_factory(company=company)
    other = await user_factory(company=company)
    for result_type in (
        RollResultType.BOTCH,
        RollResultType.BOTCH,
        RollResultType.SUCCESS,
        RollResultType.SUCCESS,
        RollResultType.SUCCESS,
        RollResultType.FAILURE,
        RollResultType.CRITICAL,
    ):
        await diceroll_factory(company=company, user=roller, total_result_type=result_type)
    await diceroll_factory(company=company, user=other, total_result_type=RollResultType.FAILURE)
    await diceroll_factory(
        company=company, user=roller, total_result_type=RollResultType.CRITICAL, is_archived=True
    )

    # When calculating statistics for the first user
    stats = await calculate_roll_statistics(
        {"user_id": roller.id, "is_archived": False, "dice_size": DiceSize.D10},
    )

    # Then each outcome is counted once per matching roll
    assert stats.total_rolls == 7
    assert (stats.botches, stats.successes, stats.failures, stats.criticals) == (2, 3, 1, 1)


async def test_outcome_counts_are_zero_without_rolls(
    company_factory: Any, user_factory: Any
) -> None:
    """Verify outcome counts default to zero when no rolls match."""
    # Given a user with no rolls
    roller = await user_factory(company=await company_factory())

    # When calculating statistics for that user
    stats = await calculate_roll_statistics({"user_id": roller.id, "is_archived": False})

    # Then every outcome count is zero
    assert (stats.botches, stats.successes, stats.failures, stats.criticals) == (0, 0, 0, 0)
