"""Character trait schemas."""

from typing import Annotated, Literal

from beanie import PydanticObjectId
from pydantic import BaseModel, Field, field_serializer

from vapi.constants import TraitModifyCurrency
from vapi.db.models import CharacterTrait, Trait
from vapi.lib.dto import COMMON_EXCLUDES


class CharacterTraitAddConstant(BaseModel):
    """Character trait model."""

    trait_id: PydanticObjectId
    value: Annotated[int, Field(ge=0, le=100)] = 0
    currency: TraitModifyCurrency


class CharacterTraitCreateCustomDTO(BaseModel):
    """Character trait model."""

    name: str
    description: str | None = None
    max_value: Annotated[int, Field(ge=0, le=100, default=5)] = 5
    min_value: Annotated[int, Field(ge=0, le=100, default=0)] = 0
    show_when_zero: bool | None = True
    parent_category_id: PydanticObjectId
    initial_cost: int | None = None
    upgrade_cost: int | None = None
    value: int | None = None


class TraitValueOptionDetail(BaseModel):
    """Detail for a single target value option."""

    direction: Literal["increase", "decrease"]
    point_change: int = Field(description="Points required (increase) or refunded (decrease)")
    can_use_xp: bool
    xp_after: int
    can_use_starting_points: bool
    starting_points_after: int


class TraitValueOptionsResponse(BaseModel):
    """Response for GET /value-options endpoint."""

    name: str
    current_value: int
    trait: Trait
    xp_current: int
    starting_points_current: int
    options: dict[str, TraitValueOptionDetail]

    @field_serializer("trait")
    def serialize_trait(self, trait: Trait) -> dict:
        """Serialize the trait."""
        return trait.model_dump(mode="json", exclude=COMMON_EXCLUDES)


class TraitModifyRequest(BaseModel):
    """Request for PUT /value endpoint."""

    target_value: int
    currency: TraitModifyCurrency


class BulkAssignTraitSuccess(BaseModel):
    """Single successfully assigned trait in a bulk operation."""

    trait_id: PydanticObjectId
    character_trait: CharacterTrait


class BulkAssignTraitFailure(BaseModel):
    """Single failed trait assignment in a bulk operation."""

    trait_id: PydanticObjectId
    error: str


class BulkAssignTraitResponse(BaseModel):
    """Response for bulk trait assignment."""

    succeeded: list[BulkAssignTraitSuccess]
    failed: list[BulkAssignTraitFailure]
