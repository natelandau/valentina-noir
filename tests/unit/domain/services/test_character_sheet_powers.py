"""Unit tests that the full sheet surfaces trait powers."""

import pytest

from vapi.domain.services.character_sheet_svc import CharacterSheetService

pytestmark = pytest.mark.anyio


async def test_full_sheet_character_trait_includes_powers(
    character_factory, trait_factory, trait_power_factory, character_trait_factory
):
    """Verify a character trait on the full sheet carries the trait's powers."""
    # Given a character with a trait that has a power
    character = await character_factory()
    trait = await trait_factory(name="Biothaumaturgy")
    await trait_power_factory(trait=trait, level=1, name="Thaumaturgical Forensics")
    await character_trait_factory(character=character, trait=trait, value=2)

    # When the full sheet is built
    sheet = await CharacterSheetService().get_character_full_sheet(character=character)

    # Then the embedded trait exposes its powers
    powers = [
        p.name
        for section in sheet.sections
        for category in section.categories
        for ct in category.character_traits
        for p in ct.trait.powers
    ]
    assert "Thaumaturgical Forensics" in powers
