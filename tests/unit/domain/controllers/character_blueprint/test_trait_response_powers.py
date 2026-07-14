"""Unit tests for powers embedded on TraitResponse."""

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
