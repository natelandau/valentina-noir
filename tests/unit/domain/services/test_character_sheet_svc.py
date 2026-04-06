"""Unit tests for CharacterSheetService."""

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from vapi.db.sql_models.character_classes import WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_sheet import CharSheetSection, Trait, TraitCategory
from vapi.domain.services import CharacterSheetService

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.sql_models.character import Character, CharacterTrait, WerewolfAttributes
    from vapi.db.sql_models.company import Company
    from vapi.domain.controllers.character.dto import CharacterFullSheetDTO


pytestmark = pytest.mark.anyio


def _collect_all_available_trait_ids(result: "CharacterFullSheetDTO") -> set[UUID]:
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
            self,
            character_factory: "Callable[..., Character]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify a character with no traits returns the full skeleton for their class/version."""
            # Given a character with no traits
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)

            # And the expected skeleton structure for the character's class/version
            char_class = character.character_class
            game_ver = character.game_version
            expected_section_count = await CharSheetSection.filter(
                is_archived=False,
                character_classes__contains=[char_class],
                game_versions__contains=[game_ver],
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
            self,
            character_factory: "Callable[..., Character]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify the skeleton only includes sections/categories for the character's class."""
            # Given a mortal and a vampire character
            company = await company_factory()
            mortal = await character_factory(character_class="MORTAL", company=company)
            vampire = await character_factory(character_class="VAMPIRE", company=company)

            # When we get the full sheet for both
            service = CharacterSheetService()
            mortal_result = await service.get_character_full_sheet(mortal)
            vampire_result = await service.get_character_full_sheet(vampire)

            # Then each sheet should match the expected section count for their class
            mortal_section_names = {s.name for s in mortal_result.sections}
            vampire_section_names = {s.name for s in vampire_result.sections}

            # And the vampire sheet should include sections specific to vampires
            vampire_only_sections = await CharSheetSection.filter(
                is_archived=False,
                character_classes__contains=["VAMPIRE"],
                game_versions__contains=[vampire.game_version],
            )
            vampire_only_names = {
                s.name for s in vampire_only_sections if "MORTAL" not in (s.character_classes or [])
            }
            for name in vampire_only_names:
                assert name in vampire_section_names
                assert name not in mortal_section_names

        async def test_skeleton_includes_empty_categories_and_subcategories(
            self,
            character_factory: "Callable[..., Character]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify the skeleton includes categories and subcategories even without traits."""
            # Given a character with no traits
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)

            # And the expected category count for one of the skeleton sections
            char_class = character.character_class
            game_ver = character.game_version
            skeleton_section = await CharSheetSection.filter(
                is_archived=False,
                character_classes__contains=[char_class],
                game_versions__contains=[game_ver],
            ).first()
            expected_category_count = await TraitCategory.filter(
                is_archived=False,
                character_classes__contains=[char_class],
                game_versions__contains=[game_ver],
                sheet_section_id=skeleton_section.id,
            ).count()

            # When we get the full sheet
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then the matching section should contain the expected number of categories
            result_section = next(s for s in result.sections if s.name == skeleton_section.name)
            assert len(result_section.categories) == expected_category_count

        async def test_traits_without_subcategory(
            self,
            character_factory: "Callable[..., Character]",
            character_trait_factory: "Callable[..., CharacterTrait]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify traits without subcategories appear directly on the category."""
            # Given a character with a trait that has no subcategory
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)
            trait = (
                await Trait.filter(
                    is_archived=False,
                    subcategory_id__isnull=True,
                    character_classes__contains=["MORTAL"],
                    game_versions__contains=[character.game_version],
                )
                .prefetch_related("category", "subcategory", "sheet_section")
                .first()
            )
            assert trait is not None
            assert trait.category_name is not None

            await character_trait_factory(character=character, trait=trait, value=3)

            # When we get the full sheet
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then the trait appears directly on the category (not in a subcategory)
            assert len(result.sections) >= 1
            category = next(
                c for s in result.sections for c in s.categories if c.name == trait.category_name
            )
            assert len(category.character_traits) == 1
            assert category.character_traits[0].id is not None
            assert category.character_traits[0].character_id == character.id
            assert category.character_traits[0].trait.id == trait.id
            assert category.character_traits[0].value == 3

        async def test_traits_with_subcategory(
            self,
            character_factory: "Callable[..., Character]",
            character_trait_factory: "Callable[..., CharacterTrait]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify traits with subcategories are nested under the correct subcategory."""
            # Given a character with a trait that belongs to a subcategory
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)
            trait = (
                await Trait.filter(
                    is_archived=False,
                    subcategory_id__not_isnull=True,
                    character_classes__contains=["MORTAL"],
                    game_versions__contains=[character.game_version],
                )
                .prefetch_related("category", "subcategory", "sheet_section")
                .first()
            )
            assert trait is not None
            assert trait.category_name is not None
            assert trait.subcategory_name is not None

            await character_trait_factory(character=character, trait=trait, value=2)

            # When we get the full sheet
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then the trait appears inside the correct subcategory
            assert len(result.sections) >= 1
            category = next(
                c for s in result.sections for c in s.categories if c.name == trait.category_name
            )
            assert len(category.subcategories) >= 1
            subcategory = next(
                sub for sub in category.subcategories if sub.name == trait.subcategory_name
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
            character_factory: "Callable[..., Character]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify skeleton sections are sorted by order."""
            # Given a character (no traits needed, skeleton is enough)
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)

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
            character_factory: "Callable[..., Character]",
            character_trait_factory: "Callable[..., CharacterTrait]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify a category can have both direct traits and subcategory traits.

            NOTE: This test skips when no category in the fixture data contains both
            direct traits (no subcategory) and subcategory traits. Currently every
            category is uniform - either all traits are direct or all are organized
            into subcategories. If the fixture data in traits.json is updated to
            include a category with both patterns, this test will run automatically.
            """
            # Given a trait with a subcategory
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)
            trait_with_sub = (
                await Trait.filter(
                    is_archived=False,
                    subcategory_id__not_isnull=True,
                    character_classes__contains=["MORTAL"],
                    game_versions__contains=[character.game_version],
                )
                .prefetch_related("category", "subcategory", "sheet_section")
                .first()
            )
            assert trait_with_sub is not None

            # And a trait without a subcategory in the same category
            trait_without_sub = (
                await Trait.filter(
                    is_archived=False,
                    subcategory_id__isnull=True,
                    category_id=trait_with_sub.category_id,  # type: ignore[attr-defined]
                )
                .prefetch_related("category", "subcategory", "sheet_section")
                .first()
            )
            if trait_without_sub is None:
                pytest.skip(
                    "No traits without subcategory in the same category as a subcategory trait"
                )

            await character_trait_factory(character=character, trait=trait_with_sub, value=2)
            await character_trait_factory(character=character, trait=trait_without_sub, value=3)

            # When we get the full sheet
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then the category should have both direct traits and subcategory traits
            category = next(
                c
                for s in result.sections
                for c in s.categories
                if c.name == trait_with_sub.category_name
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

        async def test_out_of_class_trait_backfills_parent_category(
            self,
            character_factory: "Callable[..., Character]",
            character_trait_factory: "Callable[..., CharacterTrait]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify a trait from a category outside the character's class backfills that category."""
            # Given a mortal character
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)

            # And the mortal skeleton categories for this game version
            mortal_categories = await TraitCategory.filter(
                is_archived=False,
                character_classes__contains=["MORTAL"],
                game_versions__contains=[character.game_version],
            )
            mortal_category_ids = {c.id for c in mortal_categories}

            # And a vampire-only trait whose category is not in the mortal skeleton
            vampire_only_trait = (
                await Trait.filter(
                    is_archived=False,
                    game_versions__contains=[character.game_version],
                    category_id__not_in=list(mortal_category_ids),
                )
                .prefetch_related("category", "subcategory", "sheet_section")
                .first()
            )

            # When we assign the out-of-class trait to the mortal
            await character_trait_factory(character=character, trait=vampire_only_trait, value=1)

            # And get the full sheet
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then the backfilled category should appear in the sheet
            result_category_names = {c.name for s in result.sections for c in s.categories}
            assert vampire_only_trait.category_name in result_category_names

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
            character_factory: "Callable[..., Character]",
            character_trait_factory: "Callable[..., CharacterTrait]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify traits from another class that share a section don't create duplicates."""
            # Given a mortal character
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)

            # And a trait from a different class that shares a section with the mortal skeleton
            mortal_sections = await CharSheetSection.filter(
                is_archived=False,
                character_classes__contains=["MORTAL"],
                game_versions__contains=[character.game_version],
            )
            mortal_section_ids = {s.id for s in mortal_sections}

            shared_trait = (
                await Trait.filter(
                    is_archived=False,
                    game_versions__contains=[character.game_version],
                    sheet_section_id__in=list(mortal_section_ids),
                )
                .prefetch_related("category", "subcategory", "sheet_section")
                .first()
            )
            await character_trait_factory(character=character, trait=shared_trait, value=2)

            # When we get the full sheet
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(character)

            # Then no section should appear more than once
            section_names = [s.name for s in result.sections]
            assert len(section_names) == len(set(section_names))

        async def test_available_traits_empty_when_flag_off(
            self,
            character_factory: "Callable[..., Character]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify available_traits is empty on all categories and subcategories when flag is off."""
            # Given a character with no traits
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)

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
            self,
            character_factory: "Callable[..., Character]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify available_traits contains matching standard traits when flag is on."""
            # Given a character with no assigned traits
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)

            # And the total count of standard traits for this character's class/version
            expected_trait_count = await Trait.filter(
                is_archived=False,
                character_classes__contains=[character.character_class],
                game_versions__contains=[character.game_version],
                is_custom=False,
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
            character_factory: "Callable[..., Character]",
            character_trait_factory: "Callable[..., CharacterTrait]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify assigned traits do not appear in available_traits."""
            # Given a character with a specific trait assigned
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)
            trait = await Trait.filter(
                is_archived=False,
                character_classes__contains=["MORTAL"],
                game_versions__contains=[character.game_version],
                is_custom=False,
            ).first()
            assert trait is not None
            await character_trait_factory(character=character, trait=trait, value=2)

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
            character_factory: "Callable[..., Character]",
            trait_factory: "Callable[..., Trait]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify custom traits do not appear in available_traits."""
            # Given a character
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)

            # And a custom trait exists for this character
            custom_trait = await trait_factory(
                is_custom=True,
                custom_for_character_id=character.id,
                character_classes=["MORTAL"],
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
            self,
            character_factory: "Callable[..., Character]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify available traits are sorted alphabetically by name."""
            # Given a character with no assigned traits
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)

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
            self,
            character_factory: "Callable[..., Character]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify traits from other character classes do not appear in available_traits."""
            # Given a mortal character
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)

            # And a vampire-only trait exists
            vampire_trait = await Trait.filter(
                is_archived=False,
                character_classes__contains=["VAMPIRE"],
                is_custom=False,
            ).first()

            # When we get the full sheet with available traits
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(
                character, include_available_traits=True
            )

            # Then the vampire trait should not appear in any available_traits list
            all_available_ids = _collect_all_available_trait_ids(result)
            if "MORTAL" not in (vampire_trait.character_classes or []):
                assert vampire_trait.id not in all_available_ids

        async def test_wrong_game_version_traits_excluded_from_available(
            self,
            character_factory: "Callable[..., Character]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify traits from a different game version do not appear in available_traits."""
            # Given a character
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)

            # And a trait that exists only for a different game version
            other_version_trait = (
                await Trait.exclude(
                    game_versions__contains=[character.game_version],
                )
                .filter(
                    is_archived=False,
                    is_custom=False,
                    character_classes__contains=[character.character_class],
                )
                .first()
            )

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
            character_factory: "Callable[..., Character]",
            character_trait_factory: "Callable[..., CharacterTrait]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify available_traits is empty when all matching standard traits are assigned."""
            # Given a character
            company = await company_factory()
            character = await character_factory(character_class="MORTAL", company=company)

            # And all matching standard traits are assigned to the character
            all_traits = await Trait.filter(
                is_archived=False,
                character_classes__contains=[character.character_class],
                game_versions__contains=[character.game_version],
                is_custom=False,
            )
            for trait in all_traits:
                await character_trait_factory(character=character, trait=trait, value=1)

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

        async def test_werewolf_available_gifts_filtered_by_tribe_and_auspice(
            self,
            character_factory: "Callable[..., Character]",
            werewolf_attributes_factory: "Callable[..., WerewolfAttributes]",
            company_factory: "Callable[..., Company]",
        ) -> None:
            """Verify werewolf available gifts include only tribe, auspice, and native gifts."""
            # Given a tribe and auspice from bootstrap data
            tribe = await WerewolfTribe.filter(is_archived=False).first()
            auspice = await WerewolfAuspice.filter(is_archived=False).first()
            assert tribe is not None
            assert auspice is not None

            # And a werewolf character with that tribe and auspice
            company = await company_factory()
            character = await character_factory(character_class="WEREWOLF", company=company)
            werewolf_attrs = await werewolf_attributes_factory(
                character=character,
                tribe=tribe,
                auspice=auspice,
            )
            # Re-fetch character with werewolf_attributes prefetched
            character = (
                await type(character)
                .filter(id=character.id)
                .prefetch_related(
                    "concept",
                    "vampire_attributes__clan",
                    "werewolf_attributes__tribe",
                    "werewolf_attributes__auspice",
                    "mage_attributes",
                    "hunter_attributes",
                    "specialties",
                )
                .first()
            )
            assert character.werewolf_attributes is not None
            tribe_id = werewolf_attrs.tribe_id  # type: ignore[attr-defined]
            auspice_id = werewolf_attrs.auspice_id  # type: ignore[attr-defined]
            assert tribe_id is not None
            assert auspice_id is not None

            # And there exist gift traits for a different tribe
            other_tribe = (
                await WerewolfTribe.filter(
                    is_archived=False,
                )
                .exclude(id=tribe_id)
                .first()
            )

            # Exclude gifts that also match the character's auspice
            other_tribe_gift = (
                await Trait.filter(
                    is_archived=False,
                    gift_tribe_id=other_tribe.id,
                    gift_is_native=False,
                )
                .exclude(gift_auspice_id=auspice_id)
                .first()
            )

            # And there exist gift traits for a different auspice
            other_auspice = (
                await WerewolfAuspice.filter(is_archived=False).exclude(id=auspice_id).first()
            )
            other_auspice_gift = None
            if other_auspice is not None:
                other_auspice_gift = (
                    await Trait.filter(
                        is_archived=False,
                        gift_auspice_id=other_auspice.id,
                        gift_is_native=False,
                    )
                    .exclude(gift_tribe_id=tribe_id)
                    .first()
                )

            # When we get the full sheet with available traits
            service = CharacterSheetService()
            result = await service.get_character_full_sheet(
                character, include_available_traits=True
            )

            # Then the available traits should not include gifts from the other tribe/auspice
            all_available_ids = _collect_all_available_trait_ids(result)
            assert other_tribe_gift.id not in all_available_ids

            if other_auspice_gift is not None:
                assert other_auspice_gift.id not in all_available_ids

            # And available gifts should only be native, matching tribe, or matching auspice
            all_available_gifts = [
                t
                for section in result.sections
                for category in section.categories
                for t in category.available_traits
                if t.gift_attributes is not None
            ] + [
                t
                for section in result.sections
                for category in section.categories
                for sub in category.subcategories
                for t in sub.available_traits
                if t.gift_attributes is not None
            ]
            for gift in all_available_gifts:
                assert (
                    gift.gift_attributes.is_native_gift
                    or gift.gift_attributes.tribe_id == tribe_id
                    or gift.gift_attributes.auspice_id == auspice_id
                ), f"Gift '{gift.name}' should not be available to this werewolf"
