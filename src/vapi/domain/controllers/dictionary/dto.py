"""Dictionary DTOs."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

import msgspec

from vapi.db.sql_models.character_sheet import TraitPower
from vapi.db.sql_models.dictionary import DictionaryTerm
from vapi.domain.controllers.character_blueprint.dto import TraitPowerResponse


class DictionaryTermCreate(msgspec.Struct):
    """Request body for creating a dictionary term."""

    term: str
    definition: str | None = None
    link: str | None = None
    synonyms: list[str] = []


class DictionaryTermPatch(msgspec.Struct):
    """Request body for updating a dictionary term.

    All fields use UNSET as default to distinguish 'not sent' from 'sent as null'.
    """

    term: str | msgspec.UnsetType = msgspec.UNSET
    definition: str | None | msgspec.UnsetType = msgspec.UNSET
    link: str | None | msgspec.UnsetType = msgspec.UNSET
    synonyms: list[str] | msgspec.UnsetType = msgspec.UNSET


class DictionaryTermResponse(msgspec.Struct):
    """Response body for a dictionary term."""

    id: UUID
    date_created: datetime
    date_modified: datetime
    term: str
    definition: str | None
    link: str | None
    synonyms: list[str]
    company_id: UUID | None
    source_type: str | None
    source_id: UUID | None
    powers: list[TraitPowerResponse]

    @classmethod
    def from_model(
        cls, m: DictionaryTerm, powers: Sequence[TraitPower] = ()
    ) -> "DictionaryTermResponse":
        """Convert a Tortoise DictionaryTerm to a response Struct.

        ``powers`` is supplied by the dictionary service for terms sourced from a
        trait; it is empty for every other term.
        """
        return cls(
            id=m.id,
            date_created=m.date_created,
            date_modified=m.date_modified,
            term=m.term,
            definition=m.definition,
            link=m.link,
            synonyms=m.synonyms or [],
            company_id=m.company_id,  # ty:ignore[unresolved-attribute]
            source_type=m.source_type.value if m.source_type else None,
            source_id=m.source_id,
            powers=[TraitPowerResponse.from_model(p) for p in powers],
        )
