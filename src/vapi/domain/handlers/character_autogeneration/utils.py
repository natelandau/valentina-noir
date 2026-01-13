"""Chargen utilities."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, assert_never

from faker import Faker

from vapi.constants import CharacterClass
from vapi.db.models import Character
from vapi.utils.math import roll_percentile

from .constants import MORTAL_CLASS_PERCENTILE, AutoGenExperienceLevel

if TYPE_CHECKING:
    from beanie import PydanticObjectId

    from .schemas import DotsPerExperienceLevel

fake = Faker()


async def generate_unique_name(company_id: PydanticObjectId) -> tuple[str, str]:
    """Generate a unique name for a character."""
    name_first = fake.first_name()
    while len(name_first) < 3:  # noqa: PLR2004
        name_first = fake.first_name()
    name_last = fake.last_name()
    while len(name_last) < 3:  # noqa: PLR2004
        name_last = fake.last_name()

    character_with_same_name = await Character.find(
        Character.name_first == name_first,
        Character.name_last == name_last,
        Character.is_archived == False,
        Character.company_id == company_id,
    ).first_or_none()

    if character_with_same_name:
        return await generate_unique_name(company_id)

    return name_first, name_last


def shuffle_and_adjust_trait_values(
    trait_values: list[int],
    experience_level: AutoGenExperienceLevel,
    dot_bonus: DotsPerExperienceLevel,
    max_value: int = 5,
) -> list[int]:
    """Shuffle and adjust trait values.

    Shuffle and adjust a list of trait values based on the experience level and dot bonus.

    Args:
        trait_values (list[int]): The trait values to shuffle and adjust.
        experience_level (AutoGenExperienceLevel): The experience level of the character.
        dot_bonus (DotsPerExperienceLevel): The dot bonus for the character.
        max_value (int): The maximum value to cap the trait values at. Defaults to 5.

    Returns:
        list[int]: The shuffled and adjusted trait values.
    """
    new_trait_values = trait_values.copy()
    match experience_level:
        case AutoGenExperienceLevel.NEW:
            num_new_dots = dot_bonus.NEW
        case AutoGenExperienceLevel.INTERMEDIATE:
            num_new_dots = dot_bonus.INTERMEDIATE
        case AutoGenExperienceLevel.ADVANCED:
            num_new_dots = dot_bonus.ADVANCED
        case AutoGenExperienceLevel.ELITE:
            num_new_dots = dot_bonus.ELITE
        case _:  # pragma: no cover
            assert_never(experience_level)

    while num_new_dots > 0:
        index = random.randint(0, len(new_trait_values) - 1)
        if new_trait_values[index] < max_value:
            new_trait_values[index] += 1
            num_new_dots -= 1

        if all(value == max_value for value in new_trait_values):
            break

    return random.sample(new_trait_values, len(new_trait_values))


def adjust_trait_value_based_on_level(
    experience_level: AutoGenExperienceLevel, value: int, max_value: int = 5, min_value: int = 1
) -> int:
    """Adjust a trait value based on the character's experience level.

    Modify the given trait value according to the character's experience level. Increment the value for advanced and elite levels, cap it for new and intermediate characters, and ensure the final value is within the valid range.

    Args:
        value (int): The initial trait value.
        max_value (int): The maximum value to cap the adjusted value at. Defaults to 5.
        min_value (int): The minimum value to cap the adjusted value at. Defaults to 1.
        experience_level (AutoGenExperienceLevel): The experience level of the character.

    Returns:
        int: The adjusted discipline value, constrained between 1 and 5.
    """
    match experience_level:
        case AutoGenExperienceLevel.NEW:
            value = min(value, 2)
        case AutoGenExperienceLevel.INTERMEDIATE:
            value = min(value, 3)
        case AutoGenExperienceLevel.ADVANCED | AutoGenExperienceLevel.ELITE:
            value += 1
        case _:  # pragma: no cover
            assert_never(experience_level)

    return max(min(value, max_value), min_value)


def get_character_class_percentile_lookup_table() -> dict[CharacterClass, tuple[int, int]]:
    """Get a character class percentile chance."""
    non_mortal_percentile = (100 - MORTAL_CLASS_PERCENTILE) / (len(CharacterClass) - 1)
    rounded_non_mortal_percentile = int(non_mortal_percentile)

    class_percentile_lookup = {CharacterClass.MORTAL: (0, MORTAL_CLASS_PERCENTILE)}

    starting_percentile = MORTAL_CLASS_PERCENTILE + 1
    for char_class in CharacterClass:
        if char_class != CharacterClass.MORTAL:
            upper_bound = min(starting_percentile + rounded_non_mortal_percentile, 100)
            class_percentile_lookup[char_class] = (
                starting_percentile,
                upper_bound,
            )
            starting_percentile = upper_bound + 1

    return class_percentile_lookup


def get_character_class_from_percentile() -> CharacterClass:
    """Get a character class from a percentile."""
    percentile = roll_percentile()
    for char_class, (
        lower_bound,
        upper_bound,
    ) in get_character_class_percentile_lookup_table().items():
        if lower_bound <= percentile <= upper_bound:
            return char_class

    # If all else fails, return MORTAL
    return CharacterClass.MORTAL


def divide_total_randomly(
    total: int,
    num: int,
    max_value: int | None = None,
    min_value: int = 0,
) -> list[int]:
    """Distribute a total value into random segments that sum to the total.

    Generate random integers that sum to a specified total while respecting minimum and maximum constraints. Use for resource allocation, character attribute generation, or any scenario requiring random distribution of a fixed total.

    Args:
        total (int): Sum to divide into segments. Must be positive.
        num (int): Number of segments to create. Must be positive.
        max_value (int | None, optional): Maximum allowed value per segment. If None, use total as maximum. Defaults to None.
        min_value (int, optional): Minimum allowed value per segment. Must be non-negative and less than max_value if specified. Defaults to 0.

    Returns:
        list[int]: Random segments that sum to total. Length equals num.

    Raises:
        ValueError: If constraints make division impossible:
            - total < num * min_value
            - max_value < min_value
            - num * max_value < total
    """
    if total < num * min_value or (max_value is not None and max_value < min_value):
        msg = "Impossible to divide under given constraints."
        raise ValueError(msg)

    if max_value is not None and num * max_value < total:
        msg = "Impossible to divide under given constraints with max_value."
        raise ValueError(msg)

    # Generate initial random segments
    segments = [random.randint(min_value, max_value or total) for _ in range(num)]
    current_total = sum(segments)

    # Adjust the segments iteratively
    while current_total != total:
        for i in range(num):
            if current_total < total and (max_value is None or segments[i] < max_value):
                increment = min(total - current_total, (max_value or total) - segments[i])
                segments[i] += increment
                current_total += increment
            elif current_total > total and segments[i] > min_value:
                decrement = min(current_total - total, segments[i] - min_value)
                segments[i] -= decrement
                current_total -= decrement

            if current_total == total:
                break

    return segments
