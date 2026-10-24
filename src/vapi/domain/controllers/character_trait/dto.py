"""Character trait DTOs — msgspec Structs for request/response bodies."""

from typing import TYPE_CHECKING, Annotated, Literal
from uuid import UUID

import msgspec

from vapi.constants import (
    DamageType,
    GameVersion,
    TrackerAction,
    TrackerType,
    TraitModifyCurrency,
)
from vapi.domain.controllers.character_blueprint.dto import TraitResponse
from vapi.lib.tracker_rules import HUMANITY_BOXES, DamageMarks, damage_track_fields

if TYPE_CHECKING:
    from vapi.db.sql_models.character import CharacterTrait, CharacterTraitSpecialty
    from vapi.db.sql_models.character_sheet import Trait


# ---------------------------------------------------------------------------
# Request Structs
# ---------------------------------------------------------------------------


class CharacterTraitAddConstant(msgspec.Struct):
    """Request body for assigning an existing trait to a character."""

    trait_id: UUID
    value: int = 0
    currency: TraitModifyCurrency = TraitModifyCurrency.NO_COST


class CharacterTraitCreateCustom(msgspec.Struct):
    """Request body for creating a custom trait on a character."""

    name: str
    category_id: UUID
    currency: TraitModifyCurrency
    description: str | None = None
    max_value: int = 5
    min_value: int = 0
    show_when_zero: bool = True
    is_rollable: bool = True
    initial_cost: int | None = None
    upgrade_cost: int | None = None


class CharacterTraitSpecialtyCreate(msgspec.Struct):
    """Request body for adding a specialty to an ability trait."""

    name: str
    currency: TraitModifyCurrency = TraitModifyCurrency.NO_COST


class CharacterTraitSpecialtyUpdate(msgspec.Struct):
    """Request body for renaming a specialty."""

    name: str


class TraitModifyRequest(msgspec.Struct):
    """Request body for modifying a trait's value."""

    target_value: int
    currency: TraitModifyCurrency


class TrackerActionRequest(msgspec.Struct):
    """Request body for applying one action to a trait tracker or health."""

    action: TrackerAction
    amount: Annotated[int, msgspec.Meta(ge=1)] = 1
    damage_type: DamageType | None = None


class TrackerStateSet(msgspec.Struct):
    """Request body for setting a trait tracker's full state.

    Only the fields for the tracker's type are accepted: ``current`` for counters,
    ``superficial`` and ``aggravated`` for damage tracks, ``stains`` for stains.
    """

    current: Annotated[int, msgspec.Meta(ge=0)] | None = None
    superficial: Annotated[int, msgspec.Meta(ge=0)] | None = None
    aggravated: Annotated[int, msgspec.Meta(ge=0)] | None = None
    stains: Annotated[int, msgspec.Meta(ge=0)] | None = None


# ---------------------------------------------------------------------------
# Response Structs
# ---------------------------------------------------------------------------


class CharacterTraitSpecialtyResponse(msgspec.Struct):
    """Response body for a character trait specialty."""

    id: UUID
    name: str
    date_created: str
    date_modified: str

    @classmethod
    def from_model(cls, m: "CharacterTraitSpecialty") -> "CharacterTraitSpecialtyResponse":
        """Convert a Tortoise CharacterTraitSpecialty to a response Struct."""
        return cls(
            id=m.id,
            name=m.name,
            date_created=m.date_created.isoformat(),
            date_modified=m.date_modified.isoformat(),
        )


def active_specialties(ct: "CharacterTrait") -> list["CharacterTraitSpecialty"]:
    """Return a character trait's non-archived specialties, oldest first.

    Returns an empty list when the relation was not prefetched so callers that do not
    embed specialties get no ``NoValuesFetched`` error. Archived rows are dropped here so the
    archive-filter policy holds regardless of which prefetch loaded them.
    """
    if not ct.specialties._fetched:  # noqa: SLF001
        return []
    return sorted(
        (s for s in ct.specialties if not s.is_archived),
        key=lambda s: s.date_created,
    )


class HealthLevelResponse(msgspec.Struct):
    """One V4 health level with its dice penalty and the damage marked on it."""

    name: str
    penalty: int | None
    mark: DamageType | None


class CounterTrackerResponse(msgspec.Struct, tag_field="type", tag="COUNTER"):
    """A trait whose current value is spent and regained in play."""

    size: int
    current: int


class DamageTrackResponse(msgspec.Struct, tag_field="type", tag="DAMAGE"):
    """A damage track: V5 Willpower and Health for both game versions.

    The V4-only fields (bashing, lethal, levels, current_penalty) are ``None`` for V5.
    """

    size: int
    superficial: int
    aggravated: int
    boxes: list[DamageType | None]
    is_impaired: bool
    bashing: int | None = None
    lethal: int | None = None
    levels: list[HealthLevelResponse] | None = None
    current_penalty: int | None = None


class StainsTrackerResponse(msgspec.Struct, tag_field="type", tag="STAINS"):
    """V5 Humanity stains."""

    humanity: int
    stain_capacity: int
    stains: int
    is_impaired: bool
    willpower_damage_applied: int | None = None


TrackerResponse = CounterTrackerResponse | DamageTrackResponse | StainsTrackerResponse


def tracker_type_for(trait: "Trait", *, game_version: GameVersion) -> TrackerType | None:
    """Return the tracker type a trait has for a game version, ``None`` when it has none.

    Custom traits never have a tracker.
    """
    if trait.custom_for_character_id:  # ty:ignore[unresolved-attribute]
        return None
    if game_version == GameVersion.V4:
        return trait.tracker_type_v4
    return trait.tracker_type_v5


def trait_marks(ct: "CharacterTrait") -> DamageMarks:
    """Return the damage marks stored on a character trait's tracker."""
    return DamageMarks(superficial=ct.tracker_superficial, aggravated=ct.tracker_aggravated)


def build_tracker_response(
    ct: "CharacterTrait", *, game_version: GameVersion
) -> TrackerResponse | None:
    """Build the tracker state for a character trait, ``None`` when the trait has no tracker.

    Requires the ``trait`` relation to be loaded.
    """
    match tracker_type_for(ct.trait, game_version=game_version):
        case TrackerType.COUNTER:
            return CounterTrackerResponse(
                size=ct.value, current=max(0, ct.value - ct.tracker_spent)
            )
        case TrackerType.DAMAGE:
            marks = trait_marks(ct)
            boxes, is_impaired = damage_track_fields(marks=marks, size=ct.value)
            return DamageTrackResponse(
                size=ct.value,
                superficial=marks.superficial,
                aggravated=marks.aggravated,
                boxes=boxes,
                is_impaired=is_impaired,
            )
        case TrackerType.STAINS:
            capacity = HUMANITY_BOXES - ct.value
            return StainsTrackerResponse(
                humanity=ct.value,
                stain_capacity=capacity,
                stains=ct.tracker_stains,
                is_impaired=ct.tracker_stains > capacity,
            )
        case _:
            return None


class CharacterTraitResponse(msgspec.Struct):
    """Response body for a character trait."""

    id: UUID
    character_id: UUID
    value: int
    trait: TraitResponse
    specialties: list[CharacterTraitSpecialtyResponse]
    tracker: TrackerResponse | None
    date_created: str
    date_modified: str

    @classmethod
    def from_model(
        cls, m: "CharacterTrait", *, game_version: GameVersion
    ) -> "CharacterTraitResponse":
        """Convert a Tortoise CharacterTrait to a response Struct.

        Requires prefetch_related(*CHARACTER_TRAIT_PREFETCH).

        Args:
            m: The character trait to convert.
            game_version: The owning character's game version, which picks the tracker.
        """
        return cls(
            id=m.id,
            character_id=m.character_id,  # ty:ignore[unresolved-attribute]
            value=m.value,
            trait=TraitResponse.from_model(m.trait),
            specialties=[
                CharacterTraitSpecialtyResponse.from_model(s) for s in active_specialties(m)
            ],
            tracker=build_tracker_response(m, game_version=game_version),
            date_created=m.date_created.isoformat(),
            date_modified=m.date_modified.isoformat(),
        )


CHARACTER_TRAIT_PREFETCH = [
    "trait",
    "trait__category",
    "trait__subcategory",
    "trait__sheet_section",
    "trait__gift_tribe",
    "trait__gift_auspice",
    "trait__powers",
    "specialties",
]


class TraitValueOptionDetail(msgspec.Struct):
    """Detail for a single target value option."""

    direction: Literal["increase", "decrease"]
    point_change: int
    can_use_xp: bool
    xp_after: int
    can_use_starting_points: bool
    starting_points_after: int


class TraitValueOptionsResponse(msgspec.Struct):
    """Response body for the value-options endpoint."""

    name: str
    current_value: int
    trait: TraitResponse
    xp_current: int
    starting_points_current: int
    options: dict[str, TraitValueOptionDetail]


class BulkAssignTraitSuccess(msgspec.Struct):
    """Single successfully assigned trait in a bulk operation."""

    trait_id: UUID
    character_trait: CharacterTraitResponse


class BulkAssignTraitFailure(msgspec.Struct):
    """Single failed trait assignment in a bulk operation."""

    trait_id: UUID
    error: str


class BulkAssignTraitResponse(msgspec.Struct):
    """Response body for bulk trait assignment."""

    succeeded: list[BulkAssignTraitSuccess]
    failed: list[BulkAssignTraitFailure]
