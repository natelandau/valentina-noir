"""Character trait DTOs — msgspec Structs for request/response bodies."""

from typing import TYPE_CHECKING, Literal
from uuid import UUID

import msgspec

from vapi.constants import TraitModifyCurrency
from vapi.domain.controllers.character_blueprint.dto import TraitResponse

if TYPE_CHECKING:
    from vapi.db.sql_models.character import CharacterTrait


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
    description: str | None = None
    max_value: int = 5
    min_value: int = 0
    show_when_zero: bool = True
    initial_cost: int | None = None
    upgrade_cost: int | None = None
    value: int | None = None


class TraitModifyRequest(msgspec.Struct):
    """Request body for modifying a trait's value."""

    target_value: int
    currency: TraitModifyCurrency


# ---------------------------------------------------------------------------
# Response Structs
# ---------------------------------------------------------------------------


class CharacterTraitResponse(msgspec.Struct):
    """Response body for a character trait."""

    id: UUID
    character_id: UUID
    value: int
    trait: TraitResponse
    date_created: str
    date_modified: str

    @classmethod
    def from_model(cls, m: "CharacterTrait") -> "CharacterTraitResponse":
        """Convert a Tortoise CharacterTrait to a response Struct.

        Requires prefetch_related(*CHARACTER_TRAIT_PREFETCH).
        """
        return cls(
            id=m.id,
            character_id=m.character_id,  # type: ignore[attr-defined]
            value=m.value,
            trait=TraitResponse.from_model(m.trait),
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
