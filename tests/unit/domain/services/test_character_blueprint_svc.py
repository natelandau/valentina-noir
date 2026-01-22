"""Test the character blueprint service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.constants import CharacterClass, GameVersion
from vapi.db.models import Character, CharSheetSection, Trait, TraitCategory
from vapi.domain.controllers.character_blueprint.schemas import TraitSort
from vapi.domain.services import CharacterBlueprintService

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.models import CharacterTrait

pytestmark = pytest.mark.anyio


class TestListSheetSections:
    """Test the list_sheet_sections method."""

    async def test_list_sheet_sections(self) -> None:
        """Verify that the list_sheet_sections method works."""
        # Get all the v5 sections
        all_v5_sections = (
            await CharSheetSection.find(
                CharSheetSection.is_archived == False,
                CharSheetSection.game_versions == GameVersion.V5,
            )
            .sort("order")
            .to_list()
        )

        # When listing all trait sections
        service = CharacterBlueprintService()
        count, sections = await service.list_sheet_sections(
            game_version=GameVersion.V5,
        )

        # Then the count should be the same as the number of v5 sections
        assert count == len(all_v5_sections)
        assert sections == all_v5_sections[:10]

    async def test_list_sheet_sections_skip_and_limit(self) -> None:
        """Verify that the list_sheet_sections method works."""
        # Get all the v5 sections
        all_v5_sections = (
            await CharSheetSection.find(
                CharSheetSection.is_archived == False,
                CharSheetSection.game_versions == GameVersion.V5,
            )
            .sort("order")
            .to_list()
        )

        # When listing all trait sections
        service = CharacterBlueprintService()
        count, sections = await service.list_sheet_sections(
            game_version=GameVersion.V5,
            limit=2,
            offset=1,
        )

        # Then the count should be the same as the number of v5 sections
        assert count == len(all_v5_sections)
        assert len(sections) == 2
        assert sections == all_v5_sections[1:3]

    async def test_list_sheet_sections_character_class(self) -> None:
        """Verify that the list_sheet_sections method works."""
        # Get all the v5 sections
        all_v5_sections = (
            await CharSheetSection.find(
                CharSheetSection.is_archived == False,
                CharSheetSection.game_versions == GameVersion.V5,
                CharSheetSection.character_classes == CharacterClass.VAMPIRE,
            )
            .sort("order")
            .to_list()
        )

        # When listing all trait sections for vampire
        service = CharacterBlueprintService()
        count, sections = await service.list_sheet_sections(
            game_version=GameVersion.V5,
            character_class=CharacterClass.VAMPIRE,
        )

        # Then the count should be the same as the number of v5 sections
        assert count == len(all_v5_sections)
        assert sections == all_v5_sections[:10]


class TestListSheetCategories:
    """Test the list_sheet_categories method."""

    async def test_list_sheet_categories(self) -> None:
        """Verify that the list_sheet_categories method works."""
        sheet_section = await CharSheetSection.find_one(
            CharSheetSection.is_archived == False,
            CharSheetSection.game_versions == GameVersion.V5,
        )
        # Get all the v5 categories for the sheet section
        all_v5_categories = await TraitCategory.find(
            TraitCategory.is_archived == False,
            TraitCategory.game_versions == GameVersion.V5,
            TraitCategory.parent_sheet_section_id == sheet_section.id,
        ).to_list()

        # When listing all trait categories for the sheet section
        service = CharacterBlueprintService()
        count, categories = await service.list_sheet_categories(
            game_version=GameVersion.V5,
            section=sheet_section,
        )

        # Then the count should be the same as the number of v5 categories
        assert count == len(all_v5_categories)
        assert categories == all_v5_categories[:10]

    async def test_list_sheet_categories_character_class(self) -> None:
        """Verify that the list_sheet_categories method works."""
        sheet_section = await CharSheetSection.find_one(
            CharSheetSection.is_archived == False,
            CharSheetSection.game_versions == GameVersion.V5,
        )
        # Get all the v5 categories for the sheet section
        all_v5_categories = await TraitCategory.find(
            TraitCategory.is_archived == False,
            TraitCategory.game_versions == GameVersion.V5,
            TraitCategory.parent_sheet_section_id == sheet_section.id,
            TraitCategory.character_classes == CharacterClass.VAMPIRE,
        ).to_list()

        # When listing all trait categories for the sheet section for vampire
        service = CharacterBlueprintService()
        count, categories = await service.list_sheet_categories(
            game_version=GameVersion.V5,
            section=sheet_section,
            character_class=CharacterClass.VAMPIRE,
        )

        # Then the count should be the same as the number of v5 categories
        assert count == len(all_v5_categories)
        assert categories == all_v5_categories[:10]

    async def test_list_sheet_categories_skip_and_limit(self) -> None:
        """Verify that the list_sheet_categories method works."""
        sheet_section = await CharSheetSection.find_one(
            CharSheetSection.is_archived == False,
            CharSheetSection.game_versions == GameVersion.V5,
        )
        # Get all the v5 categories for the sheet section
        all_v5_categories = await TraitCategory.find(
            TraitCategory.is_archived == False,
            TraitCategory.game_versions == GameVersion.V5,
            TraitCategory.parent_sheet_section_id == sheet_section.id,
        ).to_list()

        # When listing all trait categories for the sheet section with skip and limit
        service = CharacterBlueprintService()
        count, categories = await service.list_sheet_categories(
            game_version=GameVersion.V5,
            section=sheet_section,
            limit=2,
            offset=1,
        )

        # Then the count should be the same as the number of v5 categories
        assert count == len(all_v5_categories)
        assert len(categories) == 2
        assert categories == all_v5_categories[1:3]


class TestListSheetCategoryTraits:
    """Test the list_sheet_category_traits method."""

    async def test_list_sheet_category_traits(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify that the list_sheet_category_traits method works."""
        sheet_section = await CharSheetSection.find_one(
            CharSheetSection.is_archived == False,
            CharSheetSection.game_versions == GameVersion.V5,
        )
        category = await TraitCategory.find_one(
            TraitCategory.is_archived == False,
            TraitCategory.game_versions == GameVersion.V5,
            TraitCategory.parent_sheet_section_id == sheet_section.id,
        )
        # Get all the v5 traits for the category
        all_v5_traits = await Trait.find(
            Trait.is_archived == False,
            Trait.game_versions == GameVersion.V5,
            Trait.parent_category_id == category.id,
        ).to_list()

        # Given a custom trait in the same category
        character = await character_factory()
        custom_trait = await trait_factory(
            name="custom trait",
            description="custom trait description",
            game_versions=[GameVersion.V5],
            parent_category_id=category.id,
            custom_for_character_id=character.id,
            min_value=0,
            max_value=5,
            show_when_zero=True,
            initial_cost=1,
            upgrade_cost=2,
            character_classes=[CharacterClass.VAMPIRE],
            is_custom=True,
        )

        # When listing all trait traits for the category
        service = CharacterBlueprintService()
        count, traits = await service.list_sheet_category_traits(
            game_version=GameVersion.V5,
            category=category,
        )

        # Then the count should be the same as the number of v5 traits
        assert count == len(all_v5_traits)
        assert traits == all_v5_traits[:10]
        assert custom_trait.id not in [trait.id for trait in traits]

    async def test_list_sheet_category_traits_character_class(self) -> None:
        """Verify that the list_sheet_category_traits method works."""
        sheet_section = await CharSheetSection.find_one(
            CharSheetSection.is_archived == False,
            CharSheetSection.game_versions == GameVersion.V5,
        )
        category = await TraitCategory.find_one(
            TraitCategory.is_archived == False,
            TraitCategory.game_versions == GameVersion.V5,
            TraitCategory.parent_sheet_section_id == sheet_section.id,
        )

        # Get all the v5 traits for the category
        all_v5_traits = await Trait.find(
            Trait.is_archived == False,
            Trait.game_versions == GameVersion.V5,
            Trait.parent_category_id == category.id,
            Trait.character_classes == CharacterClass.VAMPIRE,
        ).to_list()

        # When listing all trait traits for the category for vampire
        service = CharacterBlueprintService()
        count, traits = await service.list_sheet_category_traits(
            game_version=GameVersion.V5,
            category=category,
            character_class=CharacterClass.VAMPIRE,
        )

        # Then the count should be the same as the number of v5 traits
        assert count == len(all_v5_traits)
        assert traits == all_v5_traits[:10]

    async def test_list_sheet_category_traits_skip_and_limit(self) -> None:
        """Verify that the list_sheet_category_traits method works."""
        sheet_section = await CharSheetSection.find_one(
            CharSheetSection.is_archived == False,
            CharSheetSection.game_versions == GameVersion.V5,
        )
        category = await TraitCategory.find_one(
            TraitCategory.is_archived == False,
            TraitCategory.game_versions == GameVersion.V5,
            TraitCategory.parent_sheet_section_id == sheet_section.id,
            TraitCategory.name == "Physical",
        )

        # Get all the v5 traits for the category
        all_v5_traits = await Trait.find(
            Trait.is_archived == False,
            Trait.game_versions == GameVersion.V5,
            Trait.parent_category_id == category.id,
        ).to_list()

        # When listing all trait traits for the category with skip and limit
        service = CharacterBlueprintService()
        count, traits = await service.list_sheet_category_traits(
            game_version=GameVersion.V5,
            category=category,
            limit=2,
            offset=1,
        )

        # Then the count should be the same as the number of v5 traits
        assert count == len(all_v5_traits)
        assert len(traits) == 2
        assert traits == all_v5_traits[1:3]

    async def test_list_sheet_category_traits_character_id(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify that the list_sheet_category_traits method works."""
        sheet_section = await CharSheetSection.find_one(
            CharSheetSection.is_archived == False,
            CharSheetSection.game_versions == GameVersion.V5,
        )
        category = await TraitCategory.find_one(
            TraitCategory.is_archived == False,
            TraitCategory.game_versions == GameVersion.V5,
            TraitCategory.parent_sheet_section_id == sheet_section.id,
        )
        # Get all the v5 traits for the category
        all_v5_traits = await Trait.find(
            Trait.is_archived == False,
            Trait.game_versions == GameVersion.V5,
            Trait.parent_category_id == category.id,
        ).to_list()

        # Given a custom trait in the same category
        character = await character_factory()
        custom_trait = await trait_factory(
            name="custom trait",
            description="custom trait description",
            game_versions=[GameVersion.V5],
            parent_category_id=category.id,
            custom_for_character_id=character.id,
            min_value=0,
            max_value=5,
            show_when_zero=True,
            initial_cost=1,
            upgrade_cost=2,
            character_classes=[CharacterClass.VAMPIRE],
            is_custom=True,
        )

        # When listing all trait traits for the category
        service = CharacterBlueprintService()
        count, traits = await service.list_sheet_category_traits(
            game_version=GameVersion.V5,
            category=category,
            character_id=character.id,
        )

        # Then the count should be the same as the number of v5 traits
        assert count == len(all_v5_traits) + 1
        assert traits == [*all_v5_traits, custom_trait]
        assert custom_trait.id in [trait.id for trait in traits]


class TestListAllTraits:
    """Test the list_all_traits method."""

    async def test_list_all_traits(self, debug: Callable[[...], None]) -> None:
        """Verify that the list_all_traits method works."""
        # Get all the v5 traits
        all_traits_limited = (
            await Trait.find(
                Trait.is_archived == False,
                Trait.custom_for_character_id == None,
            )
            .sort("name")
            .limit(10)
            .to_list()
        )
        all_traits_count = await Trait.find(
            Trait.is_archived == False,
            Trait.custom_for_character_id == None,
        ).count()
        # debug([x.name for x in all_traits_limited])

        # When listing all trait traits
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits()

        # Then the count should be the same as the number of v5 traits
        assert count == all_traits_count
        assert traits == all_traits_limited
        for trait in traits:
            assert trait.name.lower().startswith("a"), f"Trait {trait.name} does not start with 'a'"

    async def test_list_all_traits_skip_and_limit(self) -> None:
        """Verify that the list_all_traits method works."""
        # Get all the v5 traits
        all_traits_limited = (
            await Trait.find(
                Trait.is_archived == False,
                Trait.custom_for_character_id == None,
            )
            .sort("name")
            .skip(2)
            .limit(5)
            .to_list()
        )
        all_traits_count = await Trait.find(
            Trait.is_archived == False,
            Trait.custom_for_character_id == None,
        ).count()

        # When listing all trait traits with skip and limit
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(limit=5, offset=2)

        # Then the count should be the same as the number of v5 traits
        assert count == all_traits_count
        assert traits == all_traits_limited

    async def test_list_all_traits_game_version_and_character_class(self) -> None:
        """Verify that the list_all_traits method works."""
        filters = [
            Trait.is_archived == False,
            Trait.custom_for_character_id == None,
            Trait.game_versions == GameVersion.V5,
            Trait.character_classes == CharacterClass.VAMPIRE,
        ]

        all_traits_limited = await Trait.find(*filters).sort("name").limit(10).to_list()
        all_traits_count = await Trait.find(*filters).count()

        # When listing all trait traits for v5
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(
            game_version=GameVersion.V5,
            character_class=CharacterClass.VAMPIRE,
            order_by=TraitSort.NAME,
        )

        # Then the count should be the same as the number of v5 traits
        assert count == all_traits_count
        assert traits == all_traits_limited

    async def test_list_all_traits_parent_category_id(self) -> None:
        """Verify that the list_all_traits method works."""
        category = await TraitCategory.find_one(TraitCategory.is_archived == False)
        all_traits_limited = (
            await Trait.find(
                Trait.is_archived == False,
                Trait.custom_for_character_id == None,
                Trait.parent_category_id == category.id,
            )
            .sort("name")
            .limit(10)
            .to_list()
        )
        all_traits_count = await Trait.find(
            Trait.is_archived == False,
            Trait.custom_for_character_id == None,
            Trait.parent_category_id == category.id,
        ).count()

        # When listing all trait traits for the category
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(
            parent_category_id=category.id,
        )

        # Then the count should be the same as the number of v5 traits
        assert count == all_traits_count
        assert traits == all_traits_limited

    @pytest.mark.clean_db
    async def test_list_all_traits_sorted_by_sheet(self, debug: Callable[[...], None]) -> None:
        """Verify that the list_all_traits method works."""
        all_traits_count = await Trait.find(
            Trait.is_archived == False,
            Trait.custom_for_character_id == None,
        ).count()

        # When listing all trait traits
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(order_by=TraitSort.SHEET)
        # debug([x.name for x in traits])

        # Then the count should be the same as the number of v5 traits
        assert count == all_traits_count

        for x in [x.name for x in traits]:
            assert x in [
                "Dexterity",
                "Stamina",
                "Strength",
                "Appearance",
                "Charisma",
                "Composure",
                "Manipulation",
                "Intelligence",
                "Perception",
                "Resolve",
                "Wits",
            ]
