"""Dictionary model."""

from __future__ import annotations

from typing import Annotated, Any

from beanie import Insert, PydanticObjectId, Replace, Save, SaveChanges, Update, before_event
from pydantic import Field, model_validator

from vapi.db.models.base import BaseDocument
from vapi.lib.exceptions import ValidationError


class DictionaryTerm(BaseDocument):
    """Dictionary model."""

    term: Annotated[
        str,
        Field(min_length=3, max_length=50),
    ]
    definition: Annotated[str | None, Field(default=None)] = None
    link: Annotated[str | None, Field(default=None)] = None
    synonyms: Annotated[list[str], Field(default_factory=list)]
    is_global: Annotated[bool, Field(default=False)] = False
    company_id: Annotated[PydanticObjectId | None, Field(examples=["68c1f7152cae3787a09a74fa"])] = (
        None
    )

    @before_event(Insert, Replace, Save, Update, SaveChanges)
    async def term_to_lowercase(self) -> None:
        """Get the slug for the user."""
        self.term = self.term.lower()

    @before_event(Insert, Replace, Save, Update, SaveChanges)
    async def synonyms_to_lowercase(self) -> None:
        """Convert the synonyms to lowercase."""
        self.synonyms = sorted(list[str]({synonym.lower() for synonym in self.synonyms}))

    @model_validator(mode="before")
    @classmethod
    def must_have_definition_or_link(cls, data: Any) -> Any:
        """Must have either a definition or a link."""
        if isinstance(data, dict) and not data.get("definition") and not data.get("link"):
            msg = "Must have either a definition or a link."
            raise ValidationError(detail=msg)

        return data
