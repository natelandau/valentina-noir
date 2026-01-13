"""Advantage category model.

Merits, flaws, and backgrounds, are grouped into advantage categories such as "Resources", "Status", "Influence", etc.
"""

from typing import Annotated

from pydantic import BeforeValidator, Field

from vapi.constants import CharacterClass
from vapi.db.models.base import BaseDocument
from vapi.lib.validation import empty_string_to_none


class AdvantageCategory(BaseDocument):
    """Advantage category model for backgrounds, merits, and flaws."""

    name: Annotated[str, Field(min_length=3, max_length=50)]
    description: Annotated[
        str | None,
        Field(min_length=3, max_length=500, default=None),
        BeforeValidator(empty_string_to_none),
    ] = None
    character_classes: list[CharacterClass] = Field(default_factory=list)
    # Requires parent means that the self-named trait must be added before any other traits in the category are valid.  For example, "Haven / Safe House" requires the "Haven / Safe House" trait to be added before "surgery" or "Hidden Armory" is valid.
    requires_parent: bool = Field(default=False)
