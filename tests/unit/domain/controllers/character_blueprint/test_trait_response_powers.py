"""Unit tests for powers embedded on TraitResponse."""

import msgspec
import pytest

from vapi.db.sql_models.character_sheet import Trait
from vapi.domain.controllers.character_blueprint.dto import TraitResponse

pytestmark = pytest.mark.anyio


async def test_trait_response_includes_prefetched_powers(trait_factory, trait_power_factory):
    """Verify TraitResponse returns level-ordered powers when they are prefetched."""
    # Given a trait with two powers prefetched
    trait = await trait_factory(name="Biothaumaturgy")
    await trait_power_factory(trait=trait, level=2, name="Second")
    await trait_power_factory(trait=trait, level=1, name="First")
    # Refetch from the DB: a freshly-created factory instance's uuid_utils.UUID id
    # does not dict-match the stdlib uuid.UUID that fetch_related uses internally.
    trait = await Trait.get(id=trait.id)
    await trait.fetch_related(
        "category", "sheet_section", "subcategory", "gift_tribe", "gift_auspice", "powers"
    )

    # When the response is built
    response = TraitResponse.from_model(trait)

    # Then powers are present and level-ordered
    assert [p.name for p in response.powers] == ["First", "Second"]
    assert response.powers[0].level == 1


async def test_trait_response_serializes_nameless_dot_descriptor(
    trait_factory, trait_power_factory
):
    """Verify a nameless per-dot descriptor round-trips through the response with a null name."""
    # Given a trait with a nameless dot descriptor (an Attribute or Skill dot value)
    trait = await trait_factory(name="Firearms")
    await trait_power_factory(
        trait=trait, level=1, name=None, description="They've fired a gun a few times."
    )
    trait = await Trait.get(id=trait.id)
    await trait.fetch_related(
        "category", "sheet_section", "subcategory", "gift_tribe", "gift_auspice", "powers"
    )

    # When the response is encoded to JSON
    response = TraitResponse.from_model(trait)
    encoded = msgspec.json.encode(response.powers[0])

    # Then the name is null and the description survives
    assert response.powers[0].name is None
    assert msgspec.json.decode(encoded)["name"] is None
    assert response.powers[0].description == "They've fired a gun a few times."


async def test_trait_response_empty_powers_when_not_prefetched(trait_factory):
    """Verify TraitResponse returns an empty powers list when the relation was not prefetched."""
    # Given a trait with only the standard relations prefetched (no powers)
    trait = await trait_factory(name="Strength")
    await trait.fetch_related(
        "category", "sheet_section", "subcategory", "gift_tribe", "gift_auspice"
    )

    # When the response is built
    response = TraitResponse.from_model(trait)

    # Then powers is an empty list rather than raising
    assert response.powers == []
