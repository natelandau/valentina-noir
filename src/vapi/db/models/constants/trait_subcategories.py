"""Trait subcategories model.

Trait subcategories are used to group traits into subcategories within a category. Used for Backgrounds, Merits, and Flaws.
"""

from typing import Annotated

from beanie import PydanticObjectId
from pydantic import BeforeValidator, Field

from vapi.constants import CharacterClass, GameVersion, HunterEdgeType
from vapi.db.models.base import BaseDocument
from vapi.lib.validation import empty_string_to_none


class TraitSubcategory(BaseDocument):
    """Trait subcategory model for backgrounds, merits, and flaws."""

    name: Annotated[str, Field(min_length=3, max_length=50)]
    description: Annotated[
        str | None,
        Field(min_length=3, max_length=1000, default=None),
        BeforeValidator(empty_string_to_none),
    ] = None
    game_versions: list[GameVersion] = Field(default_factory=list)
    show_when_empty: Annotated[bool, Field(default=True)] = True
    initial_cost: Annotated[int, Field(ge=0, le=100, default=1)] = 1
    upgrade_cost: Annotated[int, Field(ge=0, le=100, default=2)] = 2
    character_classes: list[CharacterClass] = Field(default_factory=list)
    # 'Requires parent' means that this subcategory must be explicitly added to a character before any child traits can be added.
    requires_parent: Annotated[bool, Field(default=False)] = False
    pool: str | None = None
    system: str | None = None
    hunter_edge_type: HunterEdgeType | None = None

    parent_category_id: PydanticObjectId | None = None
    parent_category_name: str | None = None
