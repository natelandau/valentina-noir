"""Dictionary model."""

from __future__ import annotations

from typing import Annotated, Any, Self

from beanie import Insert, PydanticObjectId, Replace, Save, SaveChanges, Update, before_event
from pydantic import Field, model_validator

from vapi.constants import DictionarySourceType  # noqa: TC001
from vapi.db.models.base import BaseDocument
from vapi.lib.exceptions import ValidationError


class DictionaryTerm(BaseDocument):
    """Dictionary model."""

    term: Annotated[str, Field(min_length=3, max_length=50)]
    definition: Annotated[str | None, Field(default=None)] = None
    link: Annotated[str | None, Field(default=None)] = None
    synonyms: Annotated[list[str], Field(default_factory=list)]
    company_id: Annotated[PydanticObjectId | None, Field(default=None)] = None
    source_type: Annotated[DictionarySourceType | None, Field(default=None)] = None
    source_id: Annotated[PydanticObjectId | None, Field(default=None)] = None

    @model_validator(mode="after")
    def source_fields_must_be_coupled(self) -> Self:
        """Ensure source_type and source_id are both set or both None."""
        if (self.source_type is None) != (self.source_id is None):
            msg = "source_type and source_id must both be set or both be None"
            raise ValueError(msg)
        return self

    @before_event(Insert, Replace, Save, Update, SaveChanges)
    async def term_to_lowercase(self) -> None:
        """Get the slug for the user."""
        self.term = self.term.lower().strip()

    @before_event(Insert, Replace, Save, Update, SaveChanges)
    async def synonyms_to_lowercase(self) -> None:
        """Convert the synonyms to lowercase."""
        self.synonyms = sorted(list[str]({synonym.lower().strip() for synonym in self.synonyms}))

    @model_validator(mode="before")
    @classmethod
    def must_have_definition_or_link(cls, data: Any) -> Any:
        """Must have either a definition or a link."""
        if isinstance(data, dict) and not data.get("definition") and not data.get("link"):
            msg = "Must have either a definition or a link."
            raise ValidationError(detail=msg)

        return data
