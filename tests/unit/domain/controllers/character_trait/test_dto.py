"""Tests for character trait DTOs."""

from vapi.constants import GameVersion
from vapi.db.sql_models.character import CharacterTrait
from vapi.domain.controllers.character.dto import FullSheetCharacterTraitDTO
from vapi.domain.controllers.character_trait.dto import (
    CHARACTER_TRAIT_PREFETCH,
    CharacterTraitResponse,
)


async def test_character_trait_response_includes_active_specialties(
    character_trait_factory, character_trait_specialty_factory
):
    """Verify archived specialties are excluded from the trait response."""
    # Given a character trait with one active and one archived specialty
    ct = await character_trait_factory()
    await character_trait_specialty_factory(character_trait=ct, name="Sniping")
    await character_trait_specialty_factory(character_trait=ct, name="Old", is_archived=True)
    ct = await CharacterTrait.get(id=ct.id).prefetch_related(*CHARACTER_TRAIT_PREFETCH)

    # When serializing
    response = CharacterTraitResponse.from_model(ct, game_version=GameVersion.V5)

    # Then only the active specialty is returned
    assert [s.name for s in response.specialties] == ["Sniping"]


async def test_character_trait_response_specialties_ordered_by_creation(
    character_trait_factory, character_trait_specialty_factory
):
    """Verify specialties are returned oldest first."""
    # Given a character trait with two specialties created in order
    ct = await character_trait_factory()
    await character_trait_specialty_factory(character_trait=ct, name="First")
    await character_trait_specialty_factory(character_trait=ct, name="Second")
    ct = await CharacterTrait.get(id=ct.id).prefetch_related(*CHARACTER_TRAIT_PREFETCH)

    # When serializing
    response = CharacterTraitResponse.from_model(ct, game_version=GameVersion.V5)

    # Then they are ordered by creation time
    assert [s.name for s in response.specialties] == ["First", "Second"]


async def test_character_trait_response_specialties_empty_when_not_prefetched(
    character_trait_factory,
):
    """Verify an unfetched specialties relation yields an empty list."""
    # Given a character trait fetched without the specialties relation
    ct = await character_trait_factory()
    ct = await CharacterTrait.get(id=ct.id).prefetch_related(
        "trait",
        "trait__category",
        "trait__subcategory",
        "trait__sheet_section",
        "trait__gift_tribe",
        "trait__gift_auspice",
        "trait__powers",
    )

    # When serializing
    response = CharacterTraitResponse.from_model(ct, game_version=GameVersion.V5)

    # Then specialties is an empty list rather than an error
    assert response.specialties == []


async def test_full_sheet_character_trait_dto_includes_active_specialties(
    character_trait_factory, character_trait_specialty_factory
):
    """Verify archived specialties are excluded from the full sheet trait DTO."""
    # Given a character trait with one active and one archived specialty
    ct = await character_trait_factory()
    await character_trait_specialty_factory(character_trait=ct, name="Sniping")
    await character_trait_specialty_factory(character_trait=ct, name="Old", is_archived=True)
    ct = await CharacterTrait.get(id=ct.id).prefetch_related(*CHARACTER_TRAIT_PREFETCH)

    # When serializing
    dto = FullSheetCharacterTraitDTO.from_model(ct, game_version=GameVersion.V5)

    # Then only the active specialty is returned
    assert [s.name for s in dto.specialties] == ["Sniping"]
