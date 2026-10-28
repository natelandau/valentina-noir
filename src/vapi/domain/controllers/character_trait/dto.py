"""Character trait DTOs — msgspec Structs for request/response bodies."""

from typing import TYPE_CHECKING, Annotated, Literal
from uuid import UUID

import msgspec

from vapi.constants import (
    TrackerAction,
    TrackerType,
    TraitModifyCurrency,
)
from vapi.domain.controllers.character_blueprint.dto import TraitResponse
from vapi.lib.tracker_rules import HUMANITY_BOXES, resolve_tracker_type

if TYPE_CHECKING:
    from vapi.db.sql_models.character import Character, CharacterTrait, CharacterTraitSpecialty
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


class TrackerStateSet(msgspec.Struct, forbid_unknown_fields=True):
    """Request body for setting a trait tracker's full state.

    Only the field for the tracker's type is accepted: ``current`` for counters and
    ``stains`` for stains. Unknown fields are rejected so that a stale or misspelled key
    fails instead of being dropped.
    """

    current: Annotated[int, msgspec.Meta(ge=0)] | None = None
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


class CounterTrackerResponse(msgspec.Struct, tag_field="type", tag="COUNTER"):
    """A trait whose current value is spent and regained in play."""

    size: int
    current: int


class StainsTrackerResponse(msgspec.Struct, tag_field="type", tag="STAINS"):
    """V5 vampire Humanity stains."""

    humanity: int
    stain_capacity: int
    stains: int


TrackerResponse = CounterTrackerResponse | StainsTrackerResponse


def tracker_type_for(trait: "Trait", *, character: "Character") -> TrackerType | None:
    """Return the tracker type a trait has for a character, ``None`` when it has none.

    The character's game version picks the trait's configured type, and its class decides
    whether Humanity tracks stains. Custom traits never have a tracker.
    """
    if trait.custom_for_character_id:  # ty:ignore[unresolved-attribute]
        return None
    return resolve_tracker_type(
        tracker_type_v4=trait.tracker_type_v4,
        tracker_type_v5=trait.tracker_type_v5,
        game_version=character.game_version,
        character_class=character.character_class,
    )


def tracker_response_for(ct: "CharacterTrait", *, tracker_type: TrackerType) -> TrackerResponse:
    """Build the tracker state of a character trait whose tracker type is already known.

    Raises:
        ValueError: If the type is not a trait tracker type.
    """
    match tracker_type:
        case TrackerType.COUNTER:
            return CounterTrackerResponse(
                size=ct.value, current=max(0, ct.value - ct.tracker_spent)
            )
        case TrackerType.STAINS:
            return StainsTrackerResponse(
                humanity=ct.value,
                stain_capacity=HUMANITY_BOXES - ct.value,
                stains=ct.tracker_stains,
            )
        case TrackerType.DAMAGE:
            msg = "DAMAGE is the health track, not a trait tracker"
            raise ValueError(msg)


def build_tracker_response(
    ct: "CharacterTrait", *, character: "Character"
) -> TrackerResponse | None:
    """Build the tracker state for a character trait, ``None`` when the trait has no tracker.

    Requires the ``trait`` relation to be loaded.
    """
    tracker_type = tracker_type_for(ct.trait, character=character)
    if tracker_type is None:
        return None
    return tracker_response_for(ct, tracker_type=tracker_type)


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
    def from_model(cls, m: "CharacterTrait", *, character: "Character") -> "CharacterTraitResponse":
        """Convert a Tortoise CharacterTrait to a response Struct.

        Requires prefetch_related(*CHARACTER_TRAIT_PREFETCH).

        Args:
            m: The character trait to convert.
            character: The owning character, whose version and class pick the tracker.
        """
        return cls(
            id=m.id,
            character_id=m.character_id,  # ty:ignore[unresolved-attribute]
            value=m.value,
            trait=TraitResponse.from_model(m.trait),
            specialties=[
                CharacterTraitSpecialtyResponse.from_model(s) for s in active_specialties(m)
            ],
            tracker=build_tracker_response(m, character=character),
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
