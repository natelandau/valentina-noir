"""Unit tests for CharacterConceptResponse."""

import msgspec
import pytest

from vapi.constants import SpecialtyType
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.domain.controllers.character_blueprint.dto import (
    CharacterConceptResponse,
    ConceptSpecialtyResponse,
)

pytestmark = pytest.mark.anyio


async def test_concept_response_types_specialties() -> None:
    """Verify each concept specialty serializes as a typed name, description, and type."""
    # Given a seeded concept with specialties
    concept = await CharacterConcept.filter(max_specialties__gt=0).first()

    # When the response is built and round-tripped through JSON
    response = CharacterConceptResponse.from_model(concept)
    decoded = msgspec.json.decode(msgspec.json.encode(response), type=CharacterConceptResponse)

    # Then every specialty is a typed struct that matches the stored data
    assert decoded.specialties
    assert all(isinstance(s, ConceptSpecialtyResponse) for s in decoded.specialties)
    assert [(s.name, s.description, s.type) for s in decoded.specialties] == [
        (s["name"], s["description"], SpecialtyType(s["type"])) for s in concept.specialties
    ]
