"""Character generation constants."""

from __future__ import annotations

from enum import Enum
from typing import Final

from .schemas import DotsPerExperienceLevel

MORTAL_CLASS_PERCENTILE: Final[int] = 59
ATTRIBUTE_DOT_DISTRIBUTION: Final[list[int]] = [1, 2, 2, 2, 2, 3, 3, 3, 4]


class AutoGenExperienceLevel(Enum):
    """Enum to specify character levels for RNG-based trait generation."""

    NEW = "NEW"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    ELITE = "ELITE"


class AbilityFocus(Enum):
    """Skill focus."""

    JACK_OF_ALL_TRADES = "JACK_OF_ALL_TRADES"
    BALANCED = "BALANCED"
    SPECIALIST = "SPECIALIST"


ABILITY_FOCUS_DOT_DISTRIBUTION: Final[dict[AbilityFocus, list[int]]] = {
    AbilityFocus.JACK_OF_ALL_TRADES: [
        3,
        2,
        2,
        2,
        2,
        2,
        2,
        2,
        2,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
    ],
    AbilityFocus.BALANCED: [3, 3, 3, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1],
    AbilityFocus.SPECIALIST: [4, 3, 3, 3, 2, 2, 2, 1, 1, 1],
}

ADVANTAGE_STARTING_DOTS = DotsPerExperienceLevel(
    NEW=7,
    INTERMEDIATE=7 + 3,
    ADVANCED=7 + 6,
    ELITE=7 + 9,
)

FLAW_STARTING_DOTS = DotsPerExperienceLevel(
    NEW=2,
    INTERMEDIATE=2,
    ADVANCED=2 + 2,
    ELITE=2 + 3,
)


ATTRIBUTE_DOT_BONUS: Final[DotsPerExperienceLevel] = DotsPerExperienceLevel(
    NEW=0, INTERMEDIATE=5, ADVANCED=10, ELITE=15
)
ABILITY_DOT_BONUS: Final[DotsPerExperienceLevel] = DotsPerExperienceLevel(
    NEW=0,
    INTERMEDIATE=5,
    ADVANCED=10,
    ELITE=15,
)

EXTRA_DISCIPLINES_MAP = {
    AutoGenExperienceLevel.NEW: 0,
    AutoGenExperienceLevel.INTERMEDIATE: 1,
    AutoGenExperienceLevel.ADVANCED: 2,
    AutoGenExperienceLevel.ELITE: 3,
}

EXTRA_WEREWOLF_GIFT_MAP = {
    AutoGenExperienceLevel.NEW: 0,
    AutoGenExperienceLevel.INTERMEDIATE: 2,
    AutoGenExperienceLevel.ADVANCED: 4,
    AutoGenExperienceLevel.ELITE: 7,
}

NUM_WEREWOLF_RITE_MAP = {
    AutoGenExperienceLevel.NEW: 1,
    AutoGenExperienceLevel.INTERMEDIATE: 2,
    AutoGenExperienceLevel.ADVANCED: 3,
    AutoGenExperienceLevel.ELITE: 4,
}

EXTRA_HUNTER_EDGE_MAP = {
    AutoGenExperienceLevel.NEW: 0,
    AutoGenExperienceLevel.INTERMEDIATE: 0,
    AutoGenExperienceLevel.ADVANCED: 1,
    AutoGenExperienceLevel.ELITE: 3,
}

EXTRA_HUNTER_EDGE_PERK_MAP = {
    AutoGenExperienceLevel.NEW: 0,
    AutoGenExperienceLevel.INTERMEDIATE: 2,
    AutoGenExperienceLevel.ADVANCED: 3,
    AutoGenExperienceLevel.ELITE: 5,
}
