"""Character trait schemas."""

from __future__ import annotations

from typing import Annotated, Literal

from beanie import PydanticObjectId  # noqa: TC002
from pydantic import BaseModel, Field

from vapi.constants import TraitModifyCurrency  # noqa: TC001


class CharacterTraitAddConstant(BaseModel):
    """Character trait model."""

    trait_id: PydanticObjectId
    value: Annotated[int, Field(ge=0, le=100)] = 0


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

    current_value: int
    min_value: int
    max_value: int
    xp_current: int
    starting_points_current: int
    options: dict[str, TraitValueOptionDetail]


class TraitModifyRequest(BaseModel):
    """Request for PUT /value endpoint."""

    target_value: int
    currency: TraitModifyCurrency
