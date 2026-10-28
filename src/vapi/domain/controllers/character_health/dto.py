"""Character health DTOs - msgspec Structs for request and response bodies."""

from typing import TYPE_CHECKING, Annotated

import msgspec

from vapi.constants import GameVersion
from vapi.lib.tracker_rules import v4_levels

if TYPE_CHECKING:
    from vapi.db.sql_models.character import Character, CharacterHealth


NonNegativeInt = Annotated[int, msgspec.Meta(ge=0)]


class HealthStateSet(msgspec.Struct, forbid_unknown_fields=True):
    """Request body for setting a character's full health state.

    Unknown fields are rejected so that a stale or misspelled key fails instead of
    being dropped.
    """

    extra_levels: NonNegativeInt = 0
    damage: NonNegativeInt = 0


class HealthLevelResponse(msgspec.Struct):
    """One V4 health level and whether it is marked."""

    name: str
    marked: bool


class HealthResponse(msgspec.Struct, tag_field="type", tag="DAMAGE"):
    """A character's health track: one damage count, plus named levels in V4.

    ``levels`` is ``None`` for V5.
    """

    size: int
    damage: int
    extra_levels: int = 0
    levels: list[HealthLevelResponse] | None = None

    @classmethod
    def from_model(cls, m: "CharacterHealth", *, character: "Character") -> "HealthResponse":
        """Convert a Tortoise CharacterHealth to a response Struct for its character.

        The character's game version decides whether the track has named V4 levels.
        """
        levels: list[HealthLevelResponse] | None = None
        if character.game_version == GameVersion.V4:
            levels = [
                HealthLevelResponse(name=name, marked=marked)
                for name, marked in v4_levels(damage=m.damage, extra_levels=m.extra_levels)
            ]
        return cls(size=m.size, damage=m.damage, extra_levels=m.extra_levels, levels=levels)
