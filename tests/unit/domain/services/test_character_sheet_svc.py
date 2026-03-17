"""Unit tests for CharacterSheetService."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from vapi.constants import CharacterClass
from vapi.db.models import (
    Character,
    CharacterTrait,
    CharSheetSection,
    Trait,
    TraitCategory,
)
from vapi.domain.services import CharacterSheetService

if TYPE_CHECKING:
    from collections.abc import Callable

    from beanie import PydanticObjectId

    from vapi.domain.controllers.character.dto import CharacterFullSheetDTO


pytestmark = pytest.mark.anyio


def _collect_all_available_trait_ids(result: CharacterFullSheetDTO) -> set[PydanticObjectId]:
    """Collect all trait IDs from available_traits across all categories and subcategories."""
    return {
        t.id
        for section in result.sections
        for category in section.categories
        for t in category.available_traits
    } | {
        t.id
        for section in result.sections
        for category in section.categories
        for sub in category.subcategories
        for t in sub.available_traits
    }


class TestCharacterSheetService:
    """Test the character sheet service."""

    class TestGetCharacterFullSheet:
        """Test the get_character_full_sheet method."""

        async def test_empty_character_returns_skeleton(
            self, character_factory: Callable[[dict[str, Any]], Character]
        ) -> None:
            """Verify a character with no traits returns the full skeleton for their class/version."""
            # Given a character with no traits
            character = await character_factory(character_class=CharacterClass.MORTAL)

            # And the expected skeleton structure for the character's class/version
            expected_section_count = await CharSheetSection.find(
                CharSheetSection.is_archived == False,
                CharSheetSection.character_classes == character.character_class,
                CharSheetSection.game_versions == character.game_version,
            ).count()

            # When we get the full sheet
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then the result contains the character and all skeleton sections
            assert result.character.id == character.id
            assert len(result.sections) == expected_section_count

            # And all sections, categories, and subcategories have id fields
            for section in result.sections:
                assert section.id is not None
                for category in section.categories:
                    assert category.id is not None
                    assert category.character_traits == []
                    for sub in category.subcategories:
                        assert sub.id is not None
                        assert sub.character_traits == []

        async def test_skeleton_matches_character_class(
            self, character_factory: Callable[[dict[str, Any]], Character]
        ) -> None:
            """Verify the skeleton only includes sections/categories for the character's class."""
            # Given a mortal and a vampire character
            mortal = await character_factory(character_class=CharacterClass.MORTAL)
            vampire = await character_factory(character_class=CharacterClass.VAMPIRE)

            # When we get the full sheet for both
            service = CharacterSheetService()
            mortal_result = await service.get_character_full_sheet(mortal)
            vampire_result = await service.get_character_full_sheet(vampire)

            # Then each sheet should match the expected section count for their class
            mortal_section_names = {s.name for s in mortal_result.sections}
            vampire_section_names = {s.name for s in vampire_result.sections}

            # And the vampire sheet should include sections specific to vampires
            vampire_only_sections = await CharSheetSection.find(
                CharSheetSection.is_archived == False,
                CharSheetSection.character_classes == CharacterClass.VAMPIRE,
                CharSheetSection.game_versions == vampire.game_version,
            ).to_list()
            vampire_only_names = {
                s.name
                for s in vampire_only_sections
                if CharacterClass.MORTAL not in s.character_classes
            }
            for name in vampire_only_names:
                assert name in vampire_section_names
                assert name not in mortal_section_names

        async def test_skeleton_includes_empty_categories_and_subcategories(
            self, character_factory: Callable[[dict[str, Any]], Character]
        ) -> None:
            """Verify the skeleton includes categories and subcategories even without traits."""
            # Given a character with no traits
            character = await character_factory(character_class=CharacterClass.MORTAL)

            # And the expected category count for one of the skeleton sections
            skeleton_section = await CharSheetSection.find_one(
                CharSheetSection.is_archived == False,
                CharSheetSection.character_classes == character.character_class,
                CharSheetSection.game_versions == character.game_version,
            )
            assert skeleton_section is not None, "Pre-seeded DB must have sections for MORTAL"

            expected_category_count = await TraitCategory.find(
                TraitCategory.is_archived == False,
                TraitCategory.character_classes == character.character_class,
                TraitCategory.game_versions == character.game_version,
                TraitCategory.parent_sheet_section_id == skeleton_section.id,
            ).count()

            # When we get the full sheet
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then the matching section should contain the expected number of categories
            result_section = next(s for s in result.sections if s.name == skeleton_section.name)
            assert len(result_section.categories) == expected_category_count

        async def test_traits_without_subcategory(
            self,
            character_factory: Callable[[dict[str, Any]], Character],
            character_trait_factory: Callable[[dict[str, Any]], CharacterTrait],
        ) -> None:
            """Verify traits without subcategories appear directly on the category."""
            # Given a character with a trait that has no subcategory
            character = await character_factory(character_class=CharacterClass.MORTAL)
            trait = await Trait.find_one(
                Trait.is_archived == False,
                Trait.trait_subcategory_id == None,
                Trait.character_classes == CharacterClass.MORTAL,
                Trait.game_versions == character.game_version,
            )
            assert trait is not None, "Pre-seeded DB must contain traits without subcategories"
            assert trait.parent_category_name is not None

            await character_trait_factory(character_id=character.id, trait=trait, value=3)

            # When we get the full sheet
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then the trait appears directly on the category (not in a subcategory)
            assert len(result.sections) >= 1
            category = next(
                c
                for s in result.sections
                for c in s.categories
                if c.name == trait.parent_category_name
            )
            assert len(category.character_traits) == 1
            assert category.character_traits[0].id is not None
            assert category.character_traits[0].character_id == character.id
            assert category.character_traits[0].trait.id == trait.id
            assert category.character_traits[0].value == 3

        async def test_traits_with_subcategory(
            self,
            character_factory: Callable[[dict[str, Any]], Character],
            character_trait_factory: Callable[[dict[str, Any]], CharacterTrait],
        ) -> None:
            """Verify traits with subcategories are nested under the correct subcategory."""
            # Given a character with a trait that belongs to a subcategory
            character = await character_factory(character_class=CharacterClass.MORTAL)
            trait = await Trait.find_one(
                Trait.is_archived == False,
                Trait.trait_subcategory_id != None,
                Trait.character_classes == CharacterClass.MORTAL,
                Trait.game_versions == character.game_version,
            )
            assert trait is not None, "Pre-seeded DB must contain traits with subcategories"
            assert trait.parent_category_name is not None
            assert trait.trait_subcategory_name is not None

            await character_trait_factory(character_id=character.id, trait=trait, value=2)

            # When we get the full sheet
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then the trait appears inside the correct subcategory
            assert len(result.sections) >= 1
            category = next(
                c
                for s in result.sections
                for c in s.categories
                if c.name == trait.parent_category_name
            )
            assert len(category.subcategories) >= 1
            subcategory = next(
                sub for sub in category.subcategories if sub.name == trait.trait_subcategory_name
            )
            assert len(subcategory.character_traits) == 1
            assert subcategory.character_traits[0].id is not None
            assert subcategory.character_traits[0].character_id == character.id
            assert subcategory.character_traits[0].trait.id == trait.id
            assert subcategory.character_traits[0].value == 2

            # And the category's direct character_traits should be empty
            assert category.character_traits == []

        async def test_sections_sorted_by_order(
            self,
            character_factory: Callable[[dict[str, Any]], Character],
        ) -> None:
            """Verify skeleton sections are sorted by order."""
            # Given a character (no traits needed, skeleton is enough)
            character = await character_factory(character_class=CharacterClass.MORTAL)

            # When we get the full sheet
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then sections should be sorted by order
            section_orders = [s.order for s in result.sections]
            assert section_orders == sorted(section_orders)

            # And categories within each section should be sorted by order
            for section in result.sections:
                category_orders = [c.order for c in section.categories]
                assert category_orders == sorted(category_orders)

        async def test_mixed_subcategory_and_direct_traits(
            self,
            character_factory: Callable[[dict[str, Any]], Character],
            character_trait_factory: Callable[[dict[str, Any]], CharacterTrait],
        ) -> None:
            """Verify a category can have both direct traits and subcategory traits."""
            # Given a trait with a subcategory
            character = await character_factory(character_class=CharacterClass.MORTAL)
            trait_with_sub = await Trait.find_one(
                Trait.is_archived == False,
                Trait.trait_subcategory_id != None,
                Trait.character_classes == CharacterClass.MORTAL,
                Trait.game_versions == character.game_version,
            )
            assert trait_with_sub is not None

            # And a trait without a subcategory in the same category
            trait_without_sub = await Trait.find_one(
                Trait.is_archived == False,
                Trait.trait_subcategory_id == None,
                Trait.parent_category_id == trait_with_sub.parent_category_id,
            )
            if trait_without_sub is None:
                pytest.skip(
                    "No traits without subcategory in the same category as a subcategory trait"
                )

            await character_trait_factory(character_id=character.id, trait=trait_with_sub, value=2)
            await character_trait_factory(
                character_id=character.id, trait=trait_without_sub, value=3
            )

            # When we get the full sheet
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then the category should have both direct traits and subcategory traits
            category = next(
                c
                for s in result.sections
                for c in s.categories
                if c.name == trait_with_sub.parent_category_name
            )
            assert len(category.character_traits) >= 1
            assert len(category.subcategories) >= 1

            # The direct trait should be in category.character_traits
            direct_trait_ids = {ct.trait.id for ct in category.character_traits}
            assert trait_without_sub.id in direct_trait_ids

            # The subcategory trait should be in a subcategory
            sub_trait_ids = {
                ct.trait.id for sub in category.subcategories for ct in sub.character_traits
            }
            assert trait_with_sub.id in sub_trait_ids

        async def test_out_of_class_trait_backfills_parent_structures(
            self,
            character_factory: Callable[[dict[str, Any]], Character],
            character_trait_factory: Callable[[dict[str, Any]], CharacterTrait],
        ) -> None:
            """Verify a trait from a different class pulls in its parent section and category."""
            # Given a mortal character
            character = await character_factory(character_class=CharacterClass.MORTAL)

            # And the mortal skeleton sections for this game version
            mortal_sections = await CharSheetSection.find(
                CharSheetSection.is_archived == False,
                CharSheetSection.character_classes == CharacterClass.MORTAL,
                CharSheetSection.game_versions == character.game_version,
            ).to_list()
            mortal_section_ids = {s.id for s in mortal_sections}

            # And a trait that belongs exclusively to a different class (e.g. vampire)
            vampire_only_trait = await Trait.find_one(
                Trait.is_archived == False,
                Trait.character_classes == CharacterClass.VAMPIRE,
                Trait.game_versions == character.game_version,
            )
            if vampire_only_trait is None:
                pytest.skip("Pre-seeded DB needs a vampire-only trait")

            # And that trait's section is not in the mortal skeleton
            if vampire_only_trait.sheet_section_id in mortal_section_ids:
                pytest.skip("Need a trait whose section is exclusive to vampires")

            # When we assign the out-of-class trait to the mortal
            await character_trait_factory(
                character_id=character.id, trait=vampire_only_trait, value=1
            )

            # And get the full sheet
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then the result should include the mortal skeleton sections
            result_section_names = {s.name for s in result.sections}
            for section in mortal_sections:
                assert section.name in result_section_names

            # And also include the backfilled section from the out-of-class trait
            backfilled_section = await CharSheetSection.get(vampire_only_trait.sheet_section_id)
            assert backfilled_section is not None
            assert backfilled_section.name in result_section_names

            # And the trait should be present in the backfilled structure
            all_trait_ids = {
                ct.trait.id
                for s in result.sections
                for c in s.categories
                for ct in c.character_traits
            } | {
                ct.trait.id
                for s in result.sections
                for c in s.categories
                for sub in c.subcategories
                for ct in sub.character_traits
            }
            assert vampire_only_trait.id in all_trait_ids

        async def test_out_of_class_trait_does_not_duplicate_shared_sections(
            self,
            character_factory: Callable[[dict[str, Any]], Character],
            character_trait_factory: Callable[[dict[str, Any]], CharacterTrait],
        ) -> None:
            """Verify traits from another class that share a section don't create duplicates."""
            # Given a mortal character
            character = await character_factory(character_class=CharacterClass.MORTAL)

            # And a trait from a different class that shares a section with the mortal skeleton
            mortal_sections = await CharSheetSection.find(
                CharSheetSection.is_archived == False,
                CharSheetSection.character_classes == CharacterClass.MORTAL,
                CharSheetSection.game_versions == character.game_version,
            ).to_list()
            mortal_section_ids = {s.id for s in mortal_sections}

            shared_trait = await Trait.find_one(
                Trait.is_archived == False,
                Trait.game_versions == character.game_version,
                {"sheet_section_id": {"$in": list(mortal_section_ids)}},
            )
            if shared_trait is None:
                pytest.skip("Pre-seeded DB needs a trait in a shared section")

            await character_trait_factory(character_id=character.id, trait=shared_trait, value=2)

            # When we get the full sheet
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then no section should appear more than once
            section_names = [s.name for s in result.sections]
            assert len(section_names) == len(set(section_names))

        async def test_available_traits_empty_when_flag_off(
            self, character_factory: Callable[[dict[str, Any]], Character]
        ) -> None:
            """Verify available_traits is empty on all categories and subcategories when flag is off."""
            # Given a character with no traits
            character = await character_factory(character_class=CharacterClass.MORTAL)

            # When we get the full sheet without include_available_traits
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then all categories and subcategories have empty available_traits
            for section in result.sections:
                for category in section.categories:
                    assert category.available_traits == []
                    for sub in category.subcategories:
                        assert sub.available_traits == []

        async def test_available_traits_populated_when_flag_on(
            self, character_factory: Callable[[dict[str, Any]], Character]
        ) -> None:
            """Verify available_traits contains matching standard traits when flag is on."""
            # Given a character with no assigned traits
            character = await character_factory(character_class=CharacterClass.MORTAL)

            # And the total count of standard traits for this character's class/version
            expected_trait_count = await Trait.find(
                Trait.is_archived == False,
                Trait.character_classes == character.character_class,
                Trait.game_versions == character.game_version,
                Trait.is_custom == False,
            ).count()

            # When we get the full sheet with include_available_traits=True
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(
                character, include_available_traits=True
            )

            # Then the total available traits across all categories and subcategories
            # equals the expected count
            total_available = sum(
                len(category.available_traits)
                + sum(len(sub.available_traits) for sub in category.subcategories)
                for section in result.sections
                for category in section.categories
            )
            assert total_available == expected_trait_count

        async def test_assigned_traits_excluded_from_available(
            self,
            character_factory: Callable[[dict[str, Any]], Character],
            character_trait_factory: Callable[[dict[str, Any]], CharacterTrait],
        ) -> None:
            """Verify assigned traits do not appear in available_traits."""
            # Given a character with a specific trait assigned
            character = await character_factory(character_class=CharacterClass.MORTAL)
            trait = await Trait.find_one(
                Trait.is_archived == False,
                Trait.character_classes == CharacterClass.MORTAL,
                Trait.game_versions == character.game_version,
                Trait.is_custom == False,
            )
            assert trait is not None
            await character_trait_factory(character_id=character.id, trait=trait, value=2)

            # When we get the full sheet with available traits
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(
                character, include_available_traits=True
            )

            # Then the assigned trait should not appear in any available_traits list
            all_available_ids = _collect_all_available_trait_ids(result)
            assert trait.id not in all_available_ids

        async def test_custom_traits_excluded_from_available(
            self,
            character_factory: Callable[[dict[str, Any]], Character],
            trait_factory: Callable[[dict[str, Any]], Trait],
        ) -> None:
            """Verify custom traits do not appear in available_traits."""
            # Given a character
            character = await character_factory(character_class=CharacterClass.MORTAL)

            # And a custom trait exists for this character
            custom_trait = await trait_factory(
                is_custom=True,
                custom_for_character_id=character.id,
                character_classes=[CharacterClass.MORTAL],
                game_versions=[character.game_version],
            )

            # When we get the full sheet with available traits
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(
                character, include_available_traits=True
            )

            # Then the custom trait should not appear in any available_traits list
            all_available_ids = _collect_all_available_trait_ids(result)
            assert custom_trait.id not in all_available_ids

        async def test_available_traits_sorted_by_name(
            self, character_factory: Callable[[dict[str, Any]], Character]
        ) -> None:
            """Verify available traits are sorted alphabetically by name."""
            # Given a character with no assigned traits
            character = await character_factory(character_class=CharacterClass.MORTAL)

            # When we get the full sheet with available traits
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(
                character, include_available_traits=True
            )

            # Then available traits in each category and subcategory are sorted by name
            for section in result.sections:
                for category in section.categories:
                    names = [t.name for t in category.available_traits]
                    assert names == sorted(names), (
                        f"Category '{category.name}' available_traits not sorted"
                    )
                    for sub in category.subcategories:
                        sub_names = [t.name for t in sub.available_traits]
                        assert sub_names == sorted(sub_names), (
                            f"Subcategory '{sub.name}' available_traits not sorted"
                        )

        async def test_out_of_class_traits_excluded_from_available(
            self, character_factory: Callable[[dict[str, Any]], Character]
        ) -> None:
            """Verify traits from other character classes do not appear in available_traits."""
            # Given a mortal character
            character = await character_factory(character_class=CharacterClass.MORTAL)

            # And a vampire-only trait exists
            vampire_trait = await Trait.find_one(
                Trait.is_archived == False,
                Trait.character_classes == CharacterClass.VAMPIRE,
                Trait.is_custom == False,
            )
            if vampire_trait is None:
                pytest.skip("Pre-seeded DB needs a vampire-only trait")

            # When we get the full sheet with available traits
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(
                character, include_available_traits=True
            )

            # Then the vampire trait should not appear in any available_traits list
            all_available_ids = _collect_all_available_trait_ids(result)
            if CharacterClass.MORTAL not in (vampire_trait.character_classes or []):
                assert vampire_trait.id not in all_available_ids

        async def test_wrong_game_version_traits_excluded_from_available(
            self, character_factory: Callable[[dict[str, Any]], Character]
        ) -> None:
            """Verify traits from a different game version do not appear in available_traits."""
            # Given a character
            character = await character_factory(character_class=CharacterClass.MORTAL)

            # And a trait that exists only for a different game version
            other_version_trait = await Trait.find_one(
                Trait.is_archived == False,
                Trait.is_custom == False,
                Trait.character_classes == character.character_class,
                {"game_versions": {"$nin": [character.game_version.value]}},
            )
            if other_version_trait is None:
                pytest.skip("Pre-seeded DB needs a trait exclusive to a different game version")

            # When we get the full sheet with available traits
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(
                character, include_available_traits=True
            )

            # Then the other-version trait should not appear
            all_available_ids = _collect_all_available_trait_ids(result)
            assert other_version_trait.id not in all_available_ids

        async def test_available_traits_empty_when_all_assigned(
            self,
            character_factory: Callable[[dict[str, Any]], Character],
            character_trait_factory: Callable[[dict[str, Any]], CharacterTrait],
        ) -> None:
            """Verify available_traits is empty when all matching standard traits are assigned."""
            # Given a character
            character = await character_factory(character_class=CharacterClass.MORTAL)

            # And all matching standard traits are assigned to the character
            all_traits = await Trait.find(
                Trait.is_archived == False,
                Trait.character_classes == character.character_class,
                Trait.game_versions == character.game_version,
                Trait.is_custom == False,
            ).to_list()
            for trait in all_traits:
                await character_trait_factory(character_id=character.id, trait=trait, value=1)

            # When we get the full sheet with available traits
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(
                character, include_available_traits=True
            )

            # Then all available_traits lists should be empty
            for section in result.sections:
                for category in section.categories:
                    assert category.available_traits == [], (
                        f"Category '{category.name}' has available traits"
                    )
                    for sub in category.subcategories:
                        assert sub.available_traits == [], (
                            f"Subcategory '{sub.name}' has available traits"
                        )
