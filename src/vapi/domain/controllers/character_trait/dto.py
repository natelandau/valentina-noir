"""Character trait schemas."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from pydantic import BaseModel, Field


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


class TraitValueDTO(BaseModel):
    """Trait value DTO."""

    num_dots: int
