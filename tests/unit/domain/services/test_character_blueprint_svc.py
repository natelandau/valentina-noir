"""Test the character blueprint service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.constants import BlueprintTraitOrderBy, CharacterClass, GameVersion
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import (
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)

if TYPE_CHECKING:
    from collections.abc import Callable
from vapi.domain.services import CharacterBlueprintService

pytestmark = pytest.mark.anyio


class TestListSheetSections:
    """Test the list_sheet_sections method."""

    async def test_list_sheet_sections(self) -> None:
        """Verify that the list_sheet_sections method returns V5 sections."""
        # Given all non-archived V5 sections
        all_v5_sections = await CharSheetSection.filter(
            is_archived=False,
            game_versions__contains=[GameVersion.V5.value],
        ).order_by("order")

        # When listing all trait sections
        service = CharacterBlueprintService()
        count, sections = await service.list_sheet_sections(
            game_version=GameVersion.V5,
        )

        # Then the count should be the same as the number of v5 sections
        assert count == len(all_v5_sections)
        assert sections == list(all_v5_sections)[:10]

    async def test_list_sheet_sections_skip_and_limit(self) -> None:
        """Verify that list_sheet_sections respects skip and limit."""
        # Given all non-archived V5 sections
        all_v5_sections = list(
            await CharSheetSection.filter(
                is_archived=False,
                game_versions__contains=[GameVersion.V5.value],
            ).order_by("order")
        )

        # When listing all trait sections with skip and limit
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

    async def test_list_sheet_sections_no_game_version(self) -> None:
        """Verify that list_sheet_sections returns all sections when no game version is specified."""
        # Given all non-archived sections
        all_sections = list(await CharSheetSection.filter(is_archived=False).order_by("order"))

        # When listing sections without a game version filter
        service = CharacterBlueprintService()
        count, sections = await service.list_sheet_sections()

        # Then all sections are returned
        assert count == len(all_sections)
        assert sections == all_sections[:10]

    async def test_list_sheet_sections_character_class(self) -> None:
        """Verify that list_sheet_sections filters by character class."""
        # Given all non-archived V5 vampire sections
        all_v5_sections = list(
            await CharSheetSection.filter(
                is_archived=False,
                game_versions__contains=[GameVersion.V5.value],
                character_classes__contains=[CharacterClass.VAMPIRE.value],
            ).order_by("order")
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
        """Verify that list_sheet_categories returns categories for a section."""
        # Given a non-archived V5 sheet section
        sheet_section = await CharSheetSection.filter(
            is_archived=False,
            game_versions__contains=[GameVersion.V5.value],
        ).first()

        # Given all V5 categories for the sheet section
        all_v5_categories = list(
            await TraitCategory.filter(
                is_archived=False,
                game_versions__contains=[GameVersion.V5.value],
                sheet_section_id=sheet_section.id,
            )
        )

        # When listing all trait categories for the sheet section
        service = CharacterBlueprintService()
        count, categories = await service.list_sheet_categories(
            game_version=GameVersion.V5,
            section_id=sheet_section.id,
        )

        # Then the count should be the same as the number of v5 categories
        assert count == len(all_v5_categories)
        assert categories == all_v5_categories[:10]

    async def test_list_sheet_categories_character_class(self) -> None:
        """Verify that list_sheet_categories filters by character class."""
        # Given a non-archived V5 sheet section
        sheet_section = await CharSheetSection.filter(
            is_archived=False,
            game_versions__contains=[GameVersion.V5.value],
        ).first()

        # Given all V5 vampire categories for the sheet section
        all_v5_categories = list(
            await TraitCategory.filter(
                is_archived=False,
                game_versions__contains=[GameVersion.V5.value],
                sheet_section_id=sheet_section.id,
                character_classes__contains=[CharacterClass.VAMPIRE.value],
            )
        )

        # When listing all trait categories for the sheet section for vampire
        service = CharacterBlueprintService()
        count, categories = await service.list_sheet_categories(
            game_version=GameVersion.V5,
            section_id=sheet_section.id,
            character_class=CharacterClass.VAMPIRE,
        )

        # Then the count should be the same as the number of v5 categories
        assert count == len(all_v5_categories)
        assert categories == all_v5_categories[:10]

    async def test_list_sheet_categories_skip_and_limit(self) -> None:
        """Verify that list_sheet_categories respects skip and limit."""
        # Given a non-archived V5 sheet section
        sheet_section = await CharSheetSection.filter(
            is_archived=False,
            game_versions__contains=[GameVersion.V5.value],
        ).first()

        # Given all V5 categories for the sheet section
        all_v5_categories = list(
            await TraitCategory.filter(
                is_archived=False,
                game_versions__contains=[GameVersion.V5.value],
                sheet_section_id=sheet_section.id,
            )
        )

        # When listing all trait categories with skip and limit
        service = CharacterBlueprintService()
        count, categories = await service.list_sheet_categories(
            game_version=GameVersion.V5,
            section_id=sheet_section.id,
            limit=2,
            offset=1,
        )

        # Then the count should be the same as the number of v5 categories
        assert count == len(all_v5_categories)
        assert len(categories) == 2
        assert categories == all_v5_categories[1:3]

    async def test_list_sheet_categories_no_filters(self) -> None:
        """Verify that list_sheet_categories returns all categories when no filters are specified."""
        # Given all non-archived categories
        total = await TraitCategory.filter(is_archived=False).count()

        # When listing categories without filters
        service = CharacterBlueprintService()
        count, categories = await service.list_sheet_categories()

        # Then the total count matches and results are paginated
        assert count == total
        assert len(categories) == min(10, total)


class TestListSheetCategorySubcategories:
    """Test the list_sheet_category_subcategories method."""

    async def test_list_sheet_category_subcategories(self) -> None:
        """Verify that list_sheet_category_subcategories returns subcategories for a category."""
        # Given a subcategory that has a parent category
        subcategory = (
            await TraitSubcategory.filter(is_archived=False).exclude(category_id=None).first()
        )
        category = await TraitCategory.filter(id=subcategory.category_id).first()
        game_version = GameVersion(category.game_versions[0])

        # Given all subcategories for this category and game version
        expected_count = await TraitSubcategory.filter(
            is_archived=False,
            game_versions__contains=[game_version.value],
            category_id=category.id,
        ).count()

        # When listing subcategories
        service = CharacterBlueprintService()
        count, subcategories = await service.list_sheet_category_subcategories(
            game_version=game_version,
            category_id=category.id,
            limit=100,
        )

        # Then the count and results match
        assert count == expected_count
        assert len(subcategories) == expected_count
        for sub in subcategories:
            assert sub.category_id == category.id

    async def test_list_sheet_category_subcategories_character_class(self) -> None:
        """Verify that list_sheet_category_subcategories filters by character class."""
        # Given a subcategory that has a parent category
        subcategory = (
            await TraitSubcategory.filter(is_archived=False).exclude(category_id=None).first()
        )
        category = await TraitCategory.filter(id=subcategory.category_id).first()
        game_version = GameVersion(category.game_versions[0])

        # Given all subcategories filtered by character class
        expected_count = await TraitSubcategory.filter(
            is_archived=False,
            game_versions__contains=[game_version.value],
            category_id=category.id,
            character_classes__contains=[CharacterClass.VAMPIRE.value],
        ).count()

        # When listing subcategories filtered by character class
        service = CharacterBlueprintService()
        count, subcategories = await service.list_sheet_category_subcategories(
            game_version=game_version,
            category_id=category.id,
            character_class=CharacterClass.VAMPIRE,
            limit=100,
        )

        # Then the results match the filtered subcategories
        assert count == expected_count
        assert len(subcategories) == expected_count

    async def test_list_sheet_category_subcategories_skip_and_limit(self) -> None:
        """Verify that list_sheet_category_subcategories respects skip and limit."""
        # Given a subcategory that has a parent category
        subcategory = (
            await TraitSubcategory.filter(is_archived=False).exclude(category_id=None).first()
        )
        category = await TraitCategory.filter(id=subcategory.category_id).first()
        game_version = GameVersion(category.game_versions[0])

        # Given the total count of subcategories for this category
        total_count = await TraitSubcategory.filter(
            is_archived=False,
            game_versions__contains=[game_version.value],
            category_id=category.id,
        ).count()

        # When listing subcategories with skip and limit
        service = CharacterBlueprintService()
        count, subcategories = await service.list_sheet_category_subcategories(
            game_version=game_version,
            category_id=category.id,
            limit=2,
            offset=1,
        )

        # Then count reflects total but results are paginated
        assert count == total_count
        assert len(subcategories) <= 2


class TestListAllTraits:
    """Test the list_all_traits method."""

    async def test_list_all_traits(self) -> None:
        """Verify that list_all_traits returns all non-custom traits."""
        # Given all non-archived, non-custom traits
        all_traits_limited = list(
            await Trait.filter(
                is_archived=False,
                custom_for_character_id=None,
            )
            .order_by("name")
            .limit(10)
        )
        all_traits_count = await Trait.filter(
            is_archived=False,
            custom_for_character_id=None,
        ).count()

        # When listing all traits
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits()

        # Then the count should be the same as the total
        assert count == all_traits_count
        assert traits == all_traits_limited
        for trait in traits:
            assert trait.name.lower().startswith("a"), f"Trait {trait.name} does not start with 'a'"

    async def test_list_all_traits_skip_and_limit(self) -> None:
        """Verify that list_all_traits respects skip and limit."""
        # Given all non-archived, non-custom traits with offset
        all_traits_limited = list(
            await Trait.filter(
                is_archived=False,
                custom_for_character_id=None,
            )
            .order_by("name")
            .offset(2)
            .limit(5)
        )
        all_traits_count = await Trait.filter(
            is_archived=False,
            custom_for_character_id=None,
        ).count()

        # When listing all traits with skip and limit
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(limit=5, offset=2)

        # Then the count should be the same as the total
        assert count == all_traits_count
        assert traits == all_traits_limited

    async def test_list_all_traits_game_version_and_character_class(self) -> None:
        """Verify that list_all_traits filters by game version and character class."""
        # Given all V5 vampire traits
        all_traits_limited = list(
            await Trait.filter(
                is_archived=False,
                custom_for_character_id=None,
                game_versions__contains=[GameVersion.V5.value],
                character_classes__contains=[CharacterClass.VAMPIRE.value],
            )
            .order_by("name")
            .limit(10)
        )
        all_traits_count = await Trait.filter(
            is_archived=False,
            custom_for_character_id=None,
            game_versions__contains=[GameVersion.V5.value],
            character_classes__contains=[CharacterClass.VAMPIRE.value],
        ).count()

        # When listing all traits for V5 vampire
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(
            game_version=GameVersion.V5,
            character_class=CharacterClass.VAMPIRE,
            order_by=BlueprintTraitOrderBy.NAME,
        )

        # Then the count should be the same as the filtered total
        assert count == all_traits_count
        assert traits == all_traits_limited

    async def test_list_all_traits_parent_category_id(self) -> None:
        """Verify that list_all_traits filters by parent category."""
        # Given a non-archived category
        category = await TraitCategory.filter(is_archived=False).first()

        # Given all traits for this category
        all_traits_limited = list(
            await Trait.filter(
                is_archived=False,
                custom_for_character_id=None,
                category_id=category.id,
            )
            .order_by("name")
            .limit(10)
        )
        all_traits_count = await Trait.filter(
            is_archived=False,
            custom_for_character_id=None,
            category_id=category.id,
        ).count()

        # When listing all traits for the category
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(
            parent_category_id=category.id,
        )

        # Then the count should be the same as the filtered total
        assert count == all_traits_count
        assert traits == all_traits_limited

    @pytest.mark.clean_db
    async def test_list_all_traits_sorted_by_sheet(self) -> None:
        """Verify that list_all_traits sorts by sheet order."""
        # Given the total non-archived, non-custom trait count
        all_traits_count = await Trait.filter(
            is_archived=False,
            custom_for_character_id=None,
        ).count()

        # When listing all traits sorted by sheet
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(order_by=BlueprintTraitOrderBy.SHEET)

        # Then the count should be the same as the total
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

    async def test_list_all_traits_is_rollable_true(self) -> None:
        """Verify that list_all_traits filters to only rollable traits."""
        # Given the expected rollable traits
        expected_count = await Trait.filter(
            is_archived=False,
            custom_for_character_id=None,
            is_rollable=True,
        ).count()
        expected_traits = list(
            await Trait.filter(
                is_archived=False,
                custom_for_character_id=None,
                is_rollable=True,
            )
            .order_by("name")
            .limit(10)
        )

        # When listing only rollable traits
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(is_rollable=True)

        # Then only rollable traits are returned
        assert count == expected_count
        assert traits == expected_traits
        for trait in traits:
            assert trait.is_rollable is True

    async def test_list_all_traits_is_rollable_false(self) -> None:
        """Verify that list_all_traits filters to only non-rollable traits."""
        # Given the expected non-rollable traits
        expected_count = await Trait.filter(
            is_archived=False,
            custom_for_character_id=None,
            is_rollable=False,
        ).count()
        expected_traits = list(
            await Trait.filter(
                is_archived=False,
                custom_for_character_id=None,
                is_rollable=False,
            )
            .order_by("name")
            .limit(10)
        )

        # When listing only non-rollable traits
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(is_rollable=False)

        # Then only non-rollable traits are returned
        assert count == expected_count
        assert traits == expected_traits
        for trait in traits:
            assert trait.is_rollable is False

    async def test_list_all_traits_is_rollable_none(self) -> None:
        """Verify that list_all_traits returns all traits when is_rollable is None."""
        # Given the expected total traits (no is_rollable filter)
        expected_count = await Trait.filter(
            is_archived=False,
            custom_for_character_id=None,
        ).count()

        # When listing traits without is_rollable filter
        service = CharacterBlueprintService()
        count, _traits = await service.list_all_traits(is_rollable=None)

        # Then all traits are returned regardless of is_rollable value
        assert count == expected_count

    @pytest.mark.clean_db
    async def test_list_all_traits_is_rollable_with_sheet_ordering(self) -> None:
        """Verify that list_all_traits filters by is_rollable when using sheet ordering."""
        # Given the expected rollable traits
        expected_count = await Trait.filter(
            is_archived=False,
            custom_for_character_id=None,
            is_rollable=True,
        ).count()

        # When listing rollable traits with sheet ordering
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(
            is_rollable=True,
            order_by=BlueprintTraitOrderBy.SHEET,
        )

        # Then the count matches and all returned traits are rollable
        assert count == expected_count
        for trait in traits:
            assert trait.is_rollable is True

    async def test_list_all_traits_subcategory_id(
        self, trait_factory: Callable[..., Trait]
    ) -> None:
        """Verify that list_all_traits filters by subcategory_id."""
        # Given a subcategory with a parent category
        subcategory = (
            await TraitSubcategory.filter(is_archived=False).exclude(category_id=None).first()
        )
        category = await TraitCategory.filter(id=subcategory.category_id).first()
        game_version = GameVersion(category.game_versions[0])

        # Given a trait assigned to the subcategory
        await trait_factory(
            name="subcategory filter test trait",
            description="trait for subcategory filter test",
            game_versions=[game_version.value],
            category=category,
            subcategory=subcategory,
            character_classes=[CharacterClass.VAMPIRE.value],
            is_custom=False,
        )

        # Given the expected count of traits for this subcategory
        expected_count = await Trait.filter(
            is_archived=False,
            custom_for_character_id=None,
            subcategory_id=subcategory.id,
        ).count()

        # When listing traits filtered by subcategory
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(
            subcategory_id=subcategory.id,
            limit=100,
        )

        # Then only traits for that subcategory are returned
        assert count == expected_count
        assert len(traits) == expected_count
        for trait in traits:
            assert trait.subcategory_id == subcategory.id

    async def test_list_all_traits_exclude_subcategory_traits(
        self, trait_factory: Callable[..., Trait]
    ) -> None:
        """Verify that list_all_traits excludes subcategory traits when flag is set."""
        # Given a subcategory exists
        subcategory = await TraitSubcategory.filter(is_archived=False).first()

        # Given a trait with a subcategory assignment
        subcategory_trait = await trait_factory(
            name="exclude subcategory test trait",
            description="trait for exclude subcategory test",
            subcategory=subcategory,
            character_classes=[CharacterClass.VAMPIRE.value],
            is_custom=False,
        )

        # Given the expected count of traits without subcategories
        expected_count = await Trait.filter(
            is_archived=False,
            custom_for_character_id=None,
            subcategory_id=None,
        ).count()

        # When listing traits with exclude_subcategory_traits=True
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(
            exclude_subcategory_traits=True,
            limit=100,
        )

        # Then subcategory traits are excluded
        assert count == expected_count
        trait_ids = [t.id for t in traits]
        assert subcategory_trait.id not in trait_ids


class TestListConcepts:
    """Test the list_concepts method."""

    async def test_list_concepts(self) -> None:
        """Verify that list_concepts returns all non-archived concepts."""
        # Given all non-archived concepts
        all_concepts = list(await CharacterConcept.filter(is_archived=False).order_by("name"))

        # When listing concepts
        service = CharacterBlueprintService()
        count, concepts = await service.list_concepts()

        # Then the count matches all concepts
        assert count == len(all_concepts)
        assert concepts == all_concepts[:10]

    async def test_list_concepts_pagination(self) -> None:
        """Verify that list_concepts respects limit and offset."""
        # Given all non-archived concepts
        all_concepts = list(await CharacterConcept.filter(is_archived=False).order_by("name"))

        # When listing concepts with pagination
        service = CharacterBlueprintService()
        count, concepts = await service.list_concepts(limit=2, offset=1)

        # Then the total count matches but results are paginated
        assert count == len(all_concepts)
        assert len(concepts) <= 2
        assert concepts == all_concepts[1:3]

    async def test_list_concepts_sorted_by_name(self) -> None:
        """Verify that list_concepts returns results sorted by name."""
        # When listing concepts
        service = CharacterBlueprintService()
        _count, concepts = await service.list_concepts(limit=100)

        # Then the results are sorted by name
        names = [c.name for c in concepts]
        assert names == sorted(names)


class TestListVampireClans:
    """Test the list_vampire_clans method."""

    async def test_list_vampire_clans(self) -> None:
        """Verify that list_vampire_clans returns all non-archived clans."""
        # Given all non-archived vampire clans
        expected_count = await VampireClan.filter(is_archived=False).count()

        # When listing all vampire clans
        service = CharacterBlueprintService()
        count, clans = await service.list_vampire_clans(limit=100)

        # Then the count matches
        assert count == expected_count
        assert len(clans) == expected_count

    async def test_list_vampire_clans_game_version(self) -> None:
        """Verify that list_vampire_clans filters by game version."""
        # Given all non-archived V5 vampire clans
        expected_count = await VampireClan.filter(
            is_archived=False,
            game_versions__contains=[GameVersion.V5.value],
        ).count()

        # When listing V5 vampire clans
        service = CharacterBlueprintService()
        count, clans = await service.list_vampire_clans(
            game_version=GameVersion.V5,
            limit=100,
        )

        # Then the count matches
        assert count == expected_count
        assert len(clans) == expected_count


class TestListWerewolfTribes:
    """Test the list_werewolf_tribes method."""

    async def test_list_werewolf_tribes(self) -> None:
        """Verify that list_werewolf_tribes returns all non-archived tribes."""
        # Given all non-archived werewolf tribes
        expected_count = await WerewolfTribe.filter(is_archived=False).count()

        # When listing all werewolf tribes
        service = CharacterBlueprintService()
        count, tribes = await service.list_werewolf_tribes(limit=100)

        # Then the count matches
        assert count == expected_count
        assert len(tribes) == expected_count

    async def test_list_werewolf_tribes_game_version(self) -> None:
        """Verify that list_werewolf_tribes filters by game version."""
        # Given all non-archived V5 werewolf tribes
        expected_count = await WerewolfTribe.filter(
            is_archived=False,
            game_versions__contains=[GameVersion.V5.value],
        ).count()

        # When listing V5 werewolf tribes
        service = CharacterBlueprintService()
        count, tribes = await service.list_werewolf_tribes(
            game_version=GameVersion.V5,
            limit=100,
        )

        # Then the count matches
        assert count == expected_count
        assert len(tribes) == expected_count


class TestListWerewolfAuspices:
    """Test the list_werewolf_auspices method."""

    async def test_list_werewolf_auspices(self) -> None:
        """Verify that list_werewolf_auspices returns all non-archived auspices."""
        # Given all non-archived werewolf auspices
        expected_count = await WerewolfAuspice.filter(is_archived=False).count()

        # When listing all werewolf auspices
        service = CharacterBlueprintService()
        count, auspices = await service.list_werewolf_auspices(limit=100)

        # Then the count matches
        assert count == expected_count
        assert len(auspices) == expected_count

    async def test_list_werewolf_auspices_game_version(self) -> None:
        """Verify that list_werewolf_auspices filters by game version."""
        # Given all non-archived V5 werewolf auspices
        expected_count = await WerewolfAuspice.filter(
            is_archived=False,
            game_versions__contains=[GameVersion.V5.value],
        ).count()

        # When listing V5 werewolf auspices
        service = CharacterBlueprintService()
        count, auspices = await service.list_werewolf_auspices(
            game_version=GameVersion.V5,
            limit=100,
        )

        # Then the count matches
        assert count == expected_count
        assert len(auspices) == expected_count
