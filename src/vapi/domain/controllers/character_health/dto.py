"""Character health DTOs - msgspec Structs for request and response bodies."""

from typing import TYPE_CHECKING, Annotated

import msgspec

from vapi.constants import GameVersion
from vapi.domain.controllers.character_trait.dto import DamageTrackResponse, HealthLevelResponse
from vapi.lib.tracker_rules import (
    DamageMarks,
    damage_track_fields,
    v4_levels,
    v4_penalty_from_levels,
)

if TYPE_CHECKING:
    from vapi.db.sql_models.character import CharacterHealth


NonNegativeInt = Annotated[int, msgspec.Meta(ge=0)]


class HealthStateSet(msgspec.Struct):
    """Request body for setting a character's full health state.

    V4 uses bashing, lethal, and aggravated; V5 uses superficial and aggravated.
    """

    extra_levels: NonNegativeInt = 0
    superficial: NonNegativeInt = 0
    aggravated: NonNegativeInt = 0
    bashing: NonNegativeInt = 0
    lethal: NonNegativeInt = 0


class HealthResponse(DamageTrackResponse, tag_field="type", tag="DAMAGE"):
    """A character's health track, a damage track plus its extra V4 levels."""

    extra_levels: int = 0

    @classmethod
    def from_model(cls, m: "CharacterHealth", *, game_version: GameVersion) -> "HealthResponse":
        """Convert a Tortoise CharacterHealth to a response Struct for a game version."""
        if game_version == GameVersion.V4:
            marks = DamageMarks(
                bashing=m.bashing, lethal=m.lethal, superficial=0, aggravated=m.aggravated
            )
            levels = v4_levels(marks=marks, extra_levels=m.extra_levels)
            boxes = [mark for _, _, mark in levels]
            return cls(
                size=m.size,
                superficial=0,
                aggravated=m.aggravated,
                boxes=boxes,
                is_impaired=levels[-1][2] is not None,
                bashing=m.bashing,
                lethal=m.lethal,
                levels=[
                    HealthLevelResponse(name=name, penalty=penalty, mark=mark)
                    for name, penalty, mark in levels
                ],
                current_penalty=v4_penalty_from_levels(levels),
                extra_levels=m.extra_levels,
            )

        marks = DamageMarks(superficial=m.superficial, aggravated=m.aggravated)
        boxes, is_impaired = damage_track_fields(marks=marks, size=m.size)
        return cls(
            size=m.size,
            superficial=m.superficial,
            aggravated=m.aggravated,
            boxes=boxes,
            is_impaired=is_impaired,
            extra_levels=m.extra_levels,
        )
