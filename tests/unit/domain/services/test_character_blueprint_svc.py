"""Test the character blueprint service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.constants import BlueprintTraitOrderBy, CharacterClass, GameVersion
from vapi.db.models import Character, CharSheetSection, Trait, TraitCategory, TraitSubcategory
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


class TestListSheetCategorySubcategories:
    """Test the list_sheet_category_subcategories method."""

    async def test_list_sheet_category_subcategories(self) -> None:
        """Verify that list_sheet_category_subcategories returns subcategories for a category."""
        # Given a category that has subcategories
        subcategory = await TraitSubcategory.find_one(
            TraitSubcategory.is_archived == False,
            TraitSubcategory.parent_category_id != None,
        )
        category = await TraitCategory.find_one(
            TraitCategory.id == subcategory.parent_category_id,
        )
        game_version = category.game_versions[0]

        # Given all subcategories for this category and game version
        expected_count = await TraitSubcategory.find(
            TraitSubcategory.is_archived == False,
            TraitSubcategory.game_versions == game_version,
            TraitSubcategory.parent_category_id == category.id,
        ).count()

        # When listing subcategories
        service = CharacterBlueprintService()
        count, subcategories = await service.list_sheet_category_subcategories(
            game_version=game_version,
            category=category,
            limit=100,
        )

        # Then the count and results match
        assert count == expected_count
        assert len(subcategories) == expected_count
        for sub in subcategories:
            assert sub.parent_category_id == category.id

    async def test_list_sheet_category_subcategories_character_class(self) -> None:
        """Verify that list_sheet_category_subcategories filters by character class."""
        # Given a category that has subcategories
        subcategory = await TraitSubcategory.find_one(
            TraitSubcategory.is_archived == False,
            TraitSubcategory.parent_category_id != None,
        )
        category = await TraitCategory.find_one(
            TraitCategory.id == subcategory.parent_category_id,
        )
        game_version = category.game_versions[0]

        # Given all subcategories filtered by character class
        expected_count = await TraitSubcategory.find(
            TraitSubcategory.is_archived == False,
            TraitSubcategory.game_versions == game_version,
            TraitSubcategory.parent_category_id == category.id,
            TraitSubcategory.character_classes == CharacterClass.VAMPIRE,
        ).count()

        # When listing subcategories filtered by character class
        service = CharacterBlueprintService()
        count, subcategories = await service.list_sheet_category_subcategories(
            game_version=game_version,
            category=category,
            character_class=CharacterClass.VAMPIRE,
            limit=100,
        )

        # Then the results match the filtered subcategories
        assert count == expected_count
        assert len(subcategories) == expected_count

    async def test_list_sheet_category_subcategories_skip_and_limit(self) -> None:
        """Verify that list_sheet_category_subcategories respects skip and limit."""
        # Given a category that has subcategories
        subcategory = await TraitSubcategory.find_one(
            TraitSubcategory.is_archived == False,
            TraitSubcategory.parent_category_id != None,
        )
        category = await TraitCategory.find_one(
            TraitCategory.id == subcategory.parent_category_id,
        )
        game_version = category.game_versions[0]

        # Given the total count of subcategories for this category
        total_count = await TraitSubcategory.find(
            TraitSubcategory.is_archived == False,
            TraitSubcategory.game_versions == game_version,
            TraitSubcategory.parent_category_id == category.id,
        ).count()

        # When listing subcategories with skip and limit
        service = CharacterBlueprintService()
        count, subcategories = await service.list_sheet_category_subcategories(
            game_version=game_version,
            category=category,
            limit=2,
            offset=1,
        )

        # Then count reflects total but results are paginated
        assert count == total_count
        assert len(subcategories) <= 2


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

    async def test_exclude_subcategory_traits(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify that exclude_subcategory_traits filters out traits belonging to subcategories."""
        # Given a section and category
        sheet_section = await CharSheetSection.find_one(
            CharSheetSection.is_archived == False,
            CharSheetSection.game_versions == GameVersion.V5,
        )
        category = await TraitCategory.find_one(
            TraitCategory.is_archived == False,
            TraitCategory.game_versions == GameVersion.V5,
            TraitCategory.parent_sheet_section_id == sheet_section.id,
        )

        # Given a real subcategory exists
        subcategory = await TraitSubcategory.find_one(TraitSubcategory.is_archived == False)

        # Given a trait with a subcategory assignment
        subcategory_trait = await trait_factory(
            name="subcategory trait",
            description="trait belonging to a subcategory",
            game_versions=[GameVersion.V5],
            parent_category_id=category.id,
            trait_subcategory_id=subcategory.id,
            min_value=0,
            max_value=5,
            show_when_zero=True,
            initial_cost=1,
            upgrade_cost=2,
            character_classes=[CharacterClass.VAMPIRE],
            is_custom=False,
        )

        # Given all traits without subcategory for this category
        all_non_subcategory_traits = await Trait.find(
            Trait.is_archived == False,
            Trait.game_versions == GameVersion.V5,
            Trait.parent_category_id == category.id,
            Trait.custom_for_character_id == None,
            Trait.trait_subcategory_id == None,
        ).to_list()

        # When listing traits with exclude_subcategory_traits=True
        service = CharacterBlueprintService()
        count, traits = await service.list_sheet_category_traits(
            game_version=GameVersion.V5,
            category=category,
            exclude_subcategory_traits=True,
        )

        # Then subcategory traits should be excluded
        assert count == len(all_non_subcategory_traits)
        assert subcategory_trait.id not in [t.id for t in traits]

    async def test_include_subcategory_traits_by_default(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify that subcategory traits are included when exclude_subcategory_traits is False."""
        # Given a section and category
        sheet_section = await CharSheetSection.find_one(
            CharSheetSection.is_archived == False,
            CharSheetSection.game_versions == GameVersion.V5,
        )
        category = await TraitCategory.find_one(
            TraitCategory.is_archived == False,
            TraitCategory.game_versions == GameVersion.V5,
            TraitCategory.parent_sheet_section_id == sheet_section.id,
        )

        # Given a real subcategory exists
        subcategory = await TraitSubcategory.find_one(TraitSubcategory.is_archived == False)

        # Given a trait with a subcategory assignment
        subcategory_trait = await trait_factory(
            name="subcategory trait included",
            description="trait belonging to a subcategory",
            game_versions=[GameVersion.V5],
            parent_category_id=category.id,
            trait_subcategory_id=subcategory.id,
            min_value=0,
            max_value=5,
            show_when_zero=True,
            initial_cost=1,
            upgrade_cost=2,
            character_classes=[CharacterClass.VAMPIRE],
            is_custom=False,
        )

        # When listing traits without excluding subcategory traits (default)
        service = CharacterBlueprintService()
        _count, traits = await service.list_sheet_category_traits(
            game_version=GameVersion.V5,
            category=category,
            exclude_subcategory_traits=False,
            limit=100,
        )

        # Then the subcategory trait should be included
        assert subcategory_trait.id in [t.id for t in traits]


class TestListSheetCategorySubcategoryTraits:
    """Test the list_sheet_category_subcategory_traits method."""

    async def test_list_subcategory_traits(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify that list_sheet_category_subcategory_traits returns traits for a subcategory."""
        # Given a subcategory with a parent category
        subcategory = await TraitSubcategory.find_one(
            TraitSubcategory.is_archived == False,
            TraitSubcategory.parent_category_id != None,
        )
        category = await TraitCategory.find_one(
            TraitCategory.id == subcategory.parent_category_id,
        )
        game_version = category.game_versions[0]

        # Given a trait assigned to the subcategory
        subcategory_trait = await trait_factory(
            name="subcategory trait for listing",
            description="trait for subcategory listing test",
            game_versions=[game_version],
            parent_category_id=category.id,
            trait_subcategory_id=subcategory.id,
            min_value=0,
            max_value=5,
            show_when_zero=True,
            initial_cost=1,
            upgrade_cost=2,
            character_classes=[CharacterClass.VAMPIRE],
            is_custom=False,
        )

        # Given the expected count of traits for this subcategory
        expected_count = await Trait.find(
            Trait.is_archived == False,
            Trait.trait_subcategory_id == subcategory.id,
            Trait.game_versions == game_version,
        ).count()

        # When listing subcategory traits
        service = CharacterBlueprintService()
        count, traits = await service.list_sheet_category_subcategory_traits(
            game_version=game_version,
            subcategory=subcategory,
            limit=100,
        )

        # Then the count and results match
        assert count == expected_count
        assert len(traits) == expected_count
        assert subcategory_trait.id in [t.id for t in traits]

    async def test_list_subcategory_traits_character_class(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify that list_sheet_category_subcategory_traits filters by character class."""
        # Given a subcategory with a parent category
        subcategory = await TraitSubcategory.find_one(
            TraitSubcategory.is_archived == False,
            TraitSubcategory.parent_category_id != None,
        )
        category = await TraitCategory.find_one(
            TraitCategory.id == subcategory.parent_category_id,
        )
        game_version = category.game_versions[0]

        # Given a trait assigned to the subcategory for a specific class
        await trait_factory(
            name="vampire subcategory trait",
            description="vampire-only subcategory trait",
            game_versions=[game_version],
            parent_category_id=category.id,
            trait_subcategory_id=subcategory.id,
            min_value=0,
            max_value=5,
            show_when_zero=True,
            initial_cost=1,
            upgrade_cost=2,
            character_classes=[CharacterClass.VAMPIRE],
            is_custom=False,
        )

        # Given the expected count filtered by character class
        expected_count = await Trait.find(
            Trait.is_archived == False,
            Trait.trait_subcategory_id == subcategory.id,
            Trait.game_versions == game_version,
            Trait.character_classes == CharacterClass.VAMPIRE,
        ).count()

        # When listing subcategory traits filtered by character class
        service = CharacterBlueprintService()
        count, traits = await service.list_sheet_category_subcategory_traits(
            game_version=game_version,
            subcategory=subcategory,
            character_class=CharacterClass.VAMPIRE,
            limit=100,
        )

        # Then the results match the filtered count
        assert count == expected_count
        assert len(traits) == expected_count

    async def test_list_subcategory_traits_skip_and_limit(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify that list_sheet_category_subcategory_traits respects skip and limit."""
        # Given a subcategory with a parent category
        subcategory = await TraitSubcategory.find_one(
            TraitSubcategory.is_archived == False,
            TraitSubcategory.parent_category_id != None,
        )
        category = await TraitCategory.find_one(
            TraitCategory.id == subcategory.parent_category_id,
        )
        game_version = category.game_versions[0]

        # Given two traits assigned to the subcategory
        for i in range(2):
            await trait_factory(
                name=f"paginated subcategory trait {i}",
                description=f"trait {i} for pagination test",
                game_versions=[game_version],
                parent_category_id=category.id,
                trait_subcategory_id=subcategory.id,
                min_value=0,
                max_value=5,
                show_when_zero=True,
                initial_cost=1,
                upgrade_cost=2,
                character_classes=[CharacterClass.VAMPIRE],
                is_custom=False,
            )

        # Given the total count
        total_count = await Trait.find(
            Trait.is_archived == False,
            Trait.trait_subcategory_id == subcategory.id,
            Trait.game_versions == game_version,
        ).count()

        # When listing with limit and offset
        service = CharacterBlueprintService()
        count, traits = await service.list_sheet_category_subcategory_traits(
            game_version=game_version,
            subcategory=subcategory,
            limit=1,
            offset=1,
        )

        # Then count reflects total but results are paginated
        assert count == total_count
        assert len(traits) <= 1


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
            order_by=BlueprintTraitOrderBy.NAME,
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
        count, traits = await service.list_all_traits(order_by=BlueprintTraitOrderBy.SHEET)
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
