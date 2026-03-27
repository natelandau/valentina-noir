"""Test sheet section controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
)

from vapi.constants import CharacterClass, GameVersion
from vapi.db.models import (
    CharacterConcept,
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)
from vapi.domain.urls import CharacterBlueprints

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

pytestmark = pytest.mark.anyio


class TestSheetSection:
    """Test sheet section controllers."""

    async def test_list_sheet_sections(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list sheet sections endpoint is working."""
        sheet_sections = await CharSheetSection.find(
            CharSheetSection.is_archived == False,
            CharSheetSection.game_versions == GameVersion.V4,
            CharSheetSection.character_classes == CharacterClass.VAMPIRE,
        ).to_list()
        # debug(sheet_section)

        response = await client.get(
            build_url(CharacterBlueprints.SECTIONS),
            headers=token_company_admin,
            params={
                "game_version": GameVersion.V4.name,
                "character_class": CharacterClass.VAMPIRE.name,
            },
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())

        assert len(response.json()["items"]) == len(sheet_sections)
        assert response.json()["items"] == [
            sheet_section.model_dump(mode="json", exclude={"is_archived", "archive_date"})
            for sheet_section in sheet_sections
        ]

    async def test_get_sheet_section(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get sheet section endpoint is working."""
        sheet_section = await CharSheetSection.find_one(
            CharSheetSection.is_archived == False,
        )
        # debug(f"{base_url}/{sheet_section.id}")

        response = await client.get(
            build_url(
                CharacterBlueprints.SECTION_DETAIL,
                section_id=sheet_section.id,
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())

        assert response.json() == sheet_section.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )


class TestSheetCategory:
    """Test sheet category controllers."""

    async def test_get_sheet_category(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get sheet category endpoint is working."""
        sheet_section = await CharSheetSection.find_one(
            CharSheetSection.is_archived == False,
        )

        trait_category = await TraitCategory.find_one(
            TraitCategory.is_archived == False,
            TraitCategory.parent_sheet_section_id == sheet_section.id,
        )
        # debug(trait_category)

        response = await client.get(
            build_url(
                CharacterBlueprints.CATEGORY_DETAIL,
                category_id=trait_category.id,
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())

        assert response.json() == trait_category.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )

    async def test_list_sheet_categories(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list sheet categories endpoint is working."""
        sheet_section = await CharSheetSection.find_one(
            CharSheetSection.is_archived == False,
        )

        trait_categories = await TraitCategory.find(
            TraitCategory.is_archived == False,
            TraitCategory.parent_sheet_section_id == sheet_section.id,
            TraitCategory.game_versions == GameVersion.V4,
            TraitCategory.character_classes == CharacterClass.VAMPIRE,
        ).to_list()
        # Create a trait category that has a different parent sheet section
        # This will not be returned in the list
        different_sheet_section = await TraitCategory.find_one(
            TraitCategory.is_archived == False,
            TraitCategory.parent_sheet_section_id != sheet_section.id,
        )

        response = await client.get(
            build_url(CharacterBlueprints.CATEGORIES),
            headers=token_company_admin,
            params={
                "game_version": GameVersion.V4.name,
                "section_id": str(sheet_section.id),
                "character_class": CharacterClass.VAMPIRE.name,
            },
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())

        assert len(response.json()["items"]) == len(trait_categories)
        assert response.json()["items"] == [
            trait_category.model_dump(mode="json", exclude={"is_archived", "archive_date"})
            for trait_category in trait_categories
        ]
        assert (
            different_sheet_section.model_dump(mode="json", exclude={"is_archived", "archive_date"})
            not in response.json()["items"]
        )


class TestSheetSubcategory:
    """Test sheet subcategory controllers."""

    async def test_list_category_subcategories(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list category subcategories endpoint is working."""
        # Given a category with subcategories
        subcategory = await TraitSubcategory.find_one(
            TraitSubcategory.is_archived == False,
            TraitSubcategory.parent_category_id != None,
        )
        category = await TraitCategory.find_one(
            TraitCategory.id == subcategory.parent_category_id,
        )
        game_version = category.game_versions[0]

        expected_count = await TraitSubcategory.find(
            TraitSubcategory.is_archived == False,
            TraitSubcategory.game_versions == game_version,
            TraitSubcategory.parent_category_id == category.id,
        ).count()

        # When requesting subcategories via the API
        response = await client.get(
            build_url(CharacterBlueprints.SUBCATEGORIES),
            headers=token_company_admin,
            params={
                "game_version": game_version.name,
                "category_id": str(category.id),
            },
        )

        # Then the response contains the expected subcategories
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json()["total"] == expected_count
        assert len(response.json()["items"]) == min(10, expected_count)
        for item in response.json()["items"]:
            assert item["parent_category_id"] == str(category.id)

    async def test_get_category_subcategory(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get category subcategory endpoint is working."""
        # Given a subcategory
        subcategory = await TraitSubcategory.find_one(
            TraitSubcategory.is_archived == False,
            TraitSubcategory.parent_category_id != None,
        )

        # When requesting the subcategory via the API
        response = await client.get(
            build_url(
                CharacterBlueprints.SUBCATEGORY_DETAIL,
                subcategory_id=subcategory.id,
            ),
            headers=token_company_admin,
        )

        # Then the response contains the expected subcategory
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json() == subcategory.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )


class TestSheetTrait:
    """Test sheet trait controllers."""

    async def test_get_sheet_trait(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get sheet trait endpoint is working."""
        trait = await Trait.find_one(Trait.is_archived == False)
        # debug(trait)

        response = await client.get(
            build_url(
                CharacterBlueprints.TRAIT_DETAIL,
                trait_id=trait.id,
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())

        assert response.json() == trait.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )

    async def test_list_all_traits(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list all character sheet traits endpoint is working."""
        response = await client.get(
            build_url(CharacterBlueprints.TRAITS),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())

        assert response.json()["total"] > 250
        assert response.json()["limit"] == 10
        assert response.json()["offset"] == 0
        assert len(response.json()["items"]) == 10
        first_alphabetical_trait = (
            await Trait.find(Trait.is_archived == False).sort("name").limit(1).to_list()
        )
        assert response.json()["items"][0]["name"] == first_alphabetical_trait[0].name


class TestClassesConceptsAndSpecificOptions:
    """Test classes, concepts, and specific options controllers."""

    async def test_list_concepts(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list concepts endpoint is working."""
        # When we list concepts
        response = await client.get(
            build_url(CharacterBlueprints.CONCEPTS),
            headers=token_company_admin,
        )
        # debug(response.json())

        # Then verify the concepts were listed successfully
        assert response.status_code == HTTP_200_OK
        concepts = (
            await CharacterConcept.find(CharacterConcept.is_archived == False)
            .sort("name")
            .to_list()
        )
        assert response.json()["total"] == len(concepts)
        assert response.json()["items"] == [
            concept.model_dump(
                mode="json",
                exclude={"is_archived", "archive_date", "company_id"},
            )
            for concept in concepts[:10]
        ]

    async def test_get_concept(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get concept endpoint is working."""
        concept = await CharacterConcept.find_one(CharacterConcept.is_archived == False)
        response = await client.get(
            build_url(CharacterBlueprints.CONCEPT_DETAIL, concept_id=concept.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json() == concept.model_dump(
            mode="json",
            exclude={"is_archived", "archive_date", "company_id"},
        )

    async def test_list_vampire_clans(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list vampire clans endpoint is working."""
        response = await client.get(
            build_url(CharacterBlueprints.VAMPIRE_CLANS),
            headers=token_company_admin,
        )
        vampire_clans = (
            await VampireClan.find(VampireClan.is_archived == False).sort("name").to_list()
        )

        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json()["total"] == len(vampire_clans)
        assert response.json()["items"] == [
            vampire_clan.model_dump(
                mode="json",
                exclude={"is_archived", "archive_date"},
            )
            for vampire_clan in vampire_clans[:10]
        ]

    async def test_get_vampire_clan(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get vampire clan endpoint is working."""
        vampire_clan = await VampireClan.find_one(VampireClan.is_archived == False)
        response = await client.get(
            build_url(CharacterBlueprints.VAMPIRE_CLAN_DETAIL, vampire_clan_id=vampire_clan.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json() == vampire_clan.model_dump(
            mode="json",
            exclude={"is_archived", "archive_date"},
        )

    async def test_list_werewolf_tribes(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list werewolf tribes endpoint is working."""
        response = await client.get(
            build_url(CharacterBlueprints.WEREWOLF_TRIBES),
            headers=token_company_admin,
        )
        werewolf_tribes = (
            await WerewolfTribe.find(WerewolfTribe.is_archived == False).sort("name").to_list()
        )

        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json()["total"] == len(werewolf_tribes)
        assert response.json()["items"] == [
            werewolf_tribe.model_dump(
                mode="json",
                exclude={"is_archived", "archive_date"},
            )
            for werewolf_tribe in werewolf_tribes[:10]
        ]

    async def test_get_werewolf_tribe(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get werewolf tribe endpoint is working."""
        werewolf_tribe = await WerewolfTribe.find_one(WerewolfTribe.is_archived == False)
        response = await client.get(
            build_url(
                CharacterBlueprints.WEREWOLF_TRIBE_DETAIL, werewolf_tribe_id=werewolf_tribe.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json() == werewolf_tribe.model_dump(
            mode="json",
            exclude={"is_archived", "archive_date"},
        )

    async def test_list_werewolf_auspices(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list werewolf auspices endpoint is working."""
        response = await client.get(
            build_url(CharacterBlueprints.WEREWOLF_AUSPICES),
            headers=token_company_admin,
        )
        werewolf_auspices = (
            await WerewolfAuspice.find(WerewolfAuspice.is_archived == False).sort("name").to_list()
        )

        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json()["total"] == len(werewolf_auspices)
        assert response.json()["items"] == [
            werewolf_auspice.model_dump(
                mode="json",
                exclude={"is_archived", "archive_date"},
            )
            for werewolf_auspice in werewolf_auspices[:10]
        ]

    async def test_get_werewolf_auspice(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get werewolf auspice endpoint is working."""
        werewolf_auspice = await WerewolfAuspice.find_one(WerewolfAuspice.is_archived == False)
        response = await client.get(
            build_url(
                CharacterBlueprints.WEREWOLF_AUSPICE_DETAIL, werewolf_auspice_id=werewolf_auspice.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json() == werewolf_auspice.model_dump(
            mode="json",
            exclude={"is_archived", "archive_date"},
        )
