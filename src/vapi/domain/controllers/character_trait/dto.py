"""Character trait DTOs — msgspec Structs for request/response bodies."""

from typing import TYPE_CHECKING, Literal
from uuid import UUID

import msgspec

from vapi.constants import TraitModifyCurrency
from vapi.domain.controllers.character_blueprint.dto import TraitResponse

if TYPE_CHECKING:
    from vapi.db.sql_models.character import CharacterTrait, CharacterTraitSpecialty


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


class CharacterTraitResponse(msgspec.Struct):
    """Response body for a character trait."""

    id: UUID
    character_id: UUID
    value: int
    trait: TraitResponse
    specialties: list[CharacterTraitSpecialtyResponse]
    date_created: str
    date_modified: str

    @classmethod
    def from_model(cls, m: "CharacterTrait") -> "CharacterTraitResponse":
        """Convert a Tortoise CharacterTrait to a response Struct.

        Requires prefetch_related(*CHARACTER_TRAIT_PREFETCH).
        """
        return cls(
            id=m.id,
            character_id=m.character_id,  # ty:ignore[unresolved-attribute]
            value=m.value,
            trait=TraitResponse.from_model(m.trait),
            specialties=[
                CharacterTraitSpecialtyResponse.from_model(s) for s in active_specialties(m)
            ],
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
