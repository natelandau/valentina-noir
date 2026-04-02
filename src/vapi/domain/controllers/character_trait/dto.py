"""Character trait DTOs — msgspec Structs for request/response bodies."""

from typing import TYPE_CHECKING, Literal
from uuid import UUID

import msgspec

from vapi.constants import TraitModifyCurrency

if TYPE_CHECKING:
    from vapi.db.sql_models.character import CharacterTrait
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
    parent_category_id: UUID
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


class TraitResponse(msgspec.Struct):
    """Trait detail embedded in character trait responses."""

    id: UUID
    name: str
    description: str | None
    max_value: int
    min_value: int
    initial_cost: int
    upgrade_cost: int
    count_based_cost_multiplier: int | None
    is_rollable: bool
    is_custom: bool
    show_when_zero: bool
    category_id: UUID
    category_name: str
    subcategory_id: UUID | None
    subcategory_name: str | None
    sheet_section_id: UUID
    sheet_section_name: str

    @classmethod
    def from_model(cls, m: "Trait") -> "TraitResponse":
        """Convert a Tortoise Trait to a response Struct.

        Requires prefetch_related("category", "subcategory", "sheet_section").
        """
        return cls(
            id=m.id,
            name=m.name,
            description=m.description,
            max_value=m.max_value,
            min_value=m.min_value,
            initial_cost=m.initial_cost,
            upgrade_cost=m.upgrade_cost,
            count_based_cost_multiplier=m.count_based_cost_multiplier,
            is_rollable=m.is_rollable,
            is_custom=m.is_custom,
            show_when_zero=m.show_when_zero,
            category_id=m.category.id,
            category_name=m.category.name,
            subcategory_id=m.subcategory.id if m.subcategory else None,
            subcategory_name=m.subcategory.name if m.subcategory else None,
            sheet_section_id=m.sheet_section.id,
            sheet_section_name=m.sheet_section.name,
        )


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

        Requires prefetch_related("trait", "trait__category", "trait__subcategory", "trait__sheet_section").
        """
        return cls(
            id=m.id,
            character_id=m.character_id,  # type: ignore[attr-defined]
            value=m.value,
            trait=TraitResponse.from_model(m.trait),
            date_created=m.date_created.isoformat(),
            date_modified=m.date_modified.isoformat(),
        )


CHARACTER_TRAIT_PREFETCH = (
    "trait",
    "trait__category",
    "trait__subcategory",
    "trait__sheet_section",
)


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
