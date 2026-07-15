"""Unit tests for how TraitResponse identifies a custom trait."""

import msgspec
import pytest

from vapi.db.sql_models.character_sheet import Trait
from vapi.domain.controllers.character_blueprint.dto import TraitResponse

pytestmark = pytest.mark.anyio


async def _refetched(trait: Trait) -> Trait:
    """Refetch a factory-built trait with the relations TraitResponse.from_model needs."""
    # A freshly-created factory instance's uuid_utils.UUID id does not dict-match the
    # stdlib uuid.UUID that fetch_related uses internally.
    trait = await Trait.get(id=trait.id)
    await trait.fetch_related(
        "category", "sheet_section", "subcategory", "gift_tribe", "gift_auspice", "powers"
    )
    return trait


async def test_trait_response_identifies_custom_trait_by_owning_character(
    trait_factory, character_factory, company_factory
):
    """Verify a character-owned trait reports that character as its owner."""
    # Given a trait owned by a character
    company = await company_factory()
    character = await character_factory(company=company)
    trait = await trait_factory(name="Owned Trait", custom_for_character_id=character.id)

    # When the response is built
    response = TraitResponse.from_model(await _refetched(trait))

    # Then the owning character identifies it as custom
    assert str(response.custom_for_character_id) == str(character.id)


async def test_trait_response_reports_no_owner_for_core_trait(trait_factory):
    """Verify a core trait reports no owning character."""
    # Given a trait with no owning character
    trait = await trait_factory(name="Global Trait")

    # When the response is built
    response = TraitResponse.from_model(await _refetched(trait))

    # Then it has no owner
    assert response.custom_for_character_id is None


async def test_trait_response_exposes_no_is_custom_field(trait_factory):
    """Verify the serialized response offers only custom_for_character_id to detect custom traits."""
    # Given any trait
    trait = await trait_factory(name="Global Trait")

    # When the response is serialized as it would be sent to a client
    payload = msgspec.json.decode(
        msgspec.json.encode(TraitResponse.from_model(await _refetched(trait)))
    )

    # Then the redundant is_custom flag is absent, leaving ownership as the only signal
    assert "is_custom" not in payload
    assert "custom_for_character_id" in payload
