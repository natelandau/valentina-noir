"""Test sheet section controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec
import pytest
from litestar.status_codes import (
    HTTP_200_OK,
)

from vapi.constants import CharacterClass, GameVersion
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import (
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)
from vapi.domain.controllers.character_blueprint.dto import (
    CharacterConceptResponse,
    CharSheetSectionResponse,
    TraitCategoryResponse,
    TraitResponse,
    TraitSubcategoryResponse,
    VampireClanResponse,
    WerewolfAuspiceResponse,
    WerewolfTribeResponse,
)
from vapi.domain.urls import CharacterBlueprints


def _sort_id_lists(items: list[dict], key: str) -> list[dict]:
    """Return items with a specific list-of-ids field sorted for stable comparison."""
    return [{**item, key: sorted(item.get(key, []))} for item in items]


if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.developer import Developer

pytestmark = pytest.mark.anyio


class TestSheetSection:
    """Test sheet section controllers."""

    async def test_list_sheet_sections(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list sheet sections endpoint is working."""
        sheet_sections = await CharSheetSection.filter(
            is_archived=False,
            game_versions__contains=[GameVersion.V4.value],
            character_classes__contains=[CharacterClass.VAMPIRE.value],
        ).order_by("order")

        response = await client.get(
            build_url(CharacterBlueprints.SECTIONS, company_id=mirror_company.id),
            headers=token_company_admin,
            params={
                "game_version": GameVersion.V4.name,
                "character_class": CharacterClass.VAMPIRE.name,
            },
        )
        assert response.status_code == HTTP_200_OK

        assert len(response.json()["items"]) == len(sheet_sections)
        assert response.json()["items"] == [
            msgspec.json.decode(msgspec.json.encode(CharSheetSectionResponse.from_model(s)))
            for s in sheet_sections
        ]

    async def test_get_sheet_section(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get sheet section endpoint is working."""
        sheet_section = await CharSheetSection.filter(is_archived=False).first()

        response = await client.get(
            build_url(
                CharacterBlueprints.SECTION_DETAIL,
                company_id=mirror_company.id,
                section_id=sheet_section.id,
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK

        assert response.json() == msgspec.json.decode(
            msgspec.json.encode(CharSheetSectionResponse.from_model(sheet_section))
        )


class TestSheetCategory:
    """Test sheet category controllers."""

    async def test_get_sheet_category(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get sheet category endpoint is working."""
        sheet_section = await CharSheetSection.filter(is_archived=False).first()

        trait_category = (
            await TraitCategory.filter(
                is_archived=False,
                sheet_section_id=sheet_section.id,
            )
            .prefetch_related("sheet_section")
            .first()
        )

        response = await client.get(
            build_url(
                CharacterBlueprints.CATEGORY_DETAIL,
                company_id=mirror_company.id,
                category_id=trait_category.id,
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK

        assert response.json() == msgspec.json.decode(
            msgspec.json.encode(TraitCategoryResponse.from_model(trait_category))
        )

    async def test_list_sheet_categories(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list sheet categories endpoint is working."""
        sheet_section = await CharSheetSection.filter(is_archived=False).first()

        trait_categories = (
            await TraitCategory.filter(
                is_archived=False,
                sheet_section_id=sheet_section.id,
                game_versions__contains=[GameVersion.V4.value],
                character_classes__contains=[CharacterClass.VAMPIRE.value],
            )
            .order_by("order")
            .prefetch_related("sheet_section")
        )
        # Verify a category with a different parent sheet section is not returned
        different_category = (
            await TraitCategory.filter(is_archived=False)
            .exclude(sheet_section_id=sheet_section.id)
            .prefetch_related("sheet_section")
            .first()
        )

        response = await client.get(
            build_url(CharacterBlueprints.CATEGORIES, company_id=mirror_company.id),
            headers=token_company_admin,
            params={
                "game_version": GameVersion.V4.name,
                "section_id": str(sheet_section.id),
                "character_class": CharacterClass.VAMPIRE.name,
            },
        )
        assert response.status_code == HTTP_200_OK

        assert len(response.json()["items"]) == len(trait_categories)
        assert response.json()["items"] == [
            msgspec.json.decode(msgspec.json.encode(TraitCategoryResponse.from_model(tc)))
            for tc in trait_categories
        ]
        different_expected = msgspec.json.decode(
            msgspec.json.encode(TraitCategoryResponse.from_model(different_category))
        )
        assert different_expected not in response.json()["items"]


class TestSheetSubcategory:
    """Test sheet subcategory controllers."""

    async def test_list_category_subcategories(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list category subcategories endpoint is working."""
        # Given a category with subcategories
        subcategory = (
            await TraitSubcategory.filter(is_archived=False).exclude(category_id=None).first()
        )
        category = await TraitCategory.filter(id=subcategory.category_id).first()
        game_version = category.game_versions[0]

        expected_count = await TraitSubcategory.filter(
            is_archived=False,
            game_versions__contains=[game_version],
            category_id=category.id,
        ).count()

        # When requesting subcategories via the API
        response = await client.get(
            build_url(CharacterBlueprints.SUBCATEGORIES, company_id=mirror_company.id),
            headers=token_company_admin,
            params={
                "game_version": GameVersion(game_version).name,
                "category_id": str(category.id),
            },
        )

        # Then the response contains the expected subcategories
        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == expected_count
        assert len(response.json()["items"]) == min(10, expected_count)
        for item in response.json()["items"]:
            assert item["parent_category_id"] == str(category.id)

    async def test_get_category_subcategory(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get category subcategory endpoint is working."""
        # Given a subcategory
        subcategory = (
            await TraitSubcategory.filter(is_archived=False)
            .exclude(category_id=None)
            .prefetch_related("category", "sheet_section")
            .first()
        )

        # When requesting the subcategory via the API
        response = await client.get(
            build_url(
                CharacterBlueprints.SUBCATEGORY_DETAIL,
                company_id=mirror_company.id,
                subcategory_id=subcategory.id,
            ),
            headers=token_company_admin,
        )

        # Then the response contains the expected subcategory
        assert response.status_code == HTTP_200_OK
        assert response.json() == msgspec.json.decode(
            msgspec.json.encode(TraitSubcategoryResponse.from_model(subcategory))
        )


class TestSheetTrait:
    """Test sheet trait controllers."""

    async def test_get_sheet_trait(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get sheet trait endpoint is working."""
        trait = (
            await Trait.filter(is_archived=False)
            .prefetch_related(
                "category", "sheet_section", "subcategory", "gift_tribe", "gift_auspice"
            )
            .first()
        )

        response = await client.get(
            build_url(
                CharacterBlueprints.TRAIT_DETAIL,
                company_id=mirror_company.id,
                trait_id=trait.id,
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK

        assert response.json() == msgspec.json.decode(
            msgspec.json.encode(TraitResponse.from_model(trait))
        )

    async def test_list_all_traits(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list all character sheet traits endpoint is working."""
        response = await client.get(
            build_url(CharacterBlueprints.TRAITS, company_id=mirror_company.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK

        assert response.json()["total"] > 250
        assert response.json()["limit"] == 10
        assert response.json()["offset"] == 0
        assert len(response.json()["items"]) == 10
        first_alphabetical_trait = (
            await Trait.filter(is_archived=False)
            .order_by("name")
            .prefetch_related(
                "category", "sheet_section", "subcategory", "gift_tribe", "gift_auspice"
            )
            .first()
        )
        assert response.json()["items"][0]["name"] == first_alphabetical_trait.name


class TestClassesConceptsAndSpecificOptions:
    """Test classes, concepts, and specific options controllers."""

    async def test_list_concepts(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list concepts endpoint is working."""
        # When we list concepts
        response = await client.get(
            build_url(CharacterBlueprints.CONCEPTS, company_id=mirror_company.id),
            headers=token_company_admin,
        )

        # Then verify the concepts were listed successfully
        assert response.status_code == HTTP_200_OK
        concepts = await CharacterConcept.filter(is_archived=False).order_by("name")
        assert response.json()["total"] == len(concepts)
        assert response.json()["items"] == [
            msgspec.json.decode(msgspec.json.encode(CharacterConceptResponse.from_model(c)))
            for c in concepts[:10]
        ]

    async def test_get_concept(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get concept endpoint is working."""
        concept = await CharacterConcept.filter(is_archived=False).first()
        response = await client.get(
            build_url(
                CharacterBlueprints.CONCEPT_DETAIL,
                company_id=mirror_company.id,
                concept_id=concept.id,
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == msgspec.json.decode(
            msgspec.json.encode(CharacterConceptResponse.from_model(concept))
        )

    async def test_list_vampire_clans(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list vampire clans endpoint is working."""
        response = await client.get(
            build_url(CharacterBlueprints.VAMPIRE_CLANS, company_id=mirror_company.id),
            headers=token_company_admin,
        )
        vampire_clans = (
            await VampireClan.filter(is_archived=False)
            .order_by("name")
            .prefetch_related("disciplines")
        )

        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == len(vampire_clans)
        assert _sort_id_lists(response.json()["items"], "discipline_ids") == _sort_id_lists(
            [
                msgspec.json.decode(msgspec.json.encode(VampireClanResponse.from_model(vc)))
                for vc in vampire_clans[:10]
            ],
            "discipline_ids",
        )

    async def test_get_vampire_clan(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get vampire clan endpoint is working."""
        vampire_clan = (
            await VampireClan.filter(is_archived=False).prefetch_related("disciplines").first()
        )
        response = await client.get(
            build_url(
                CharacterBlueprints.VAMPIRE_CLAN_DETAIL,
                company_id=mirror_company.id,
                vampire_clan_id=vampire_clan.id,
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        data = response.json()
        expected = msgspec.json.decode(
            msgspec.json.encode(VampireClanResponse.from_model(vampire_clan))
        )
        data["discipline_ids"] = sorted(data["discipline_ids"])
        expected["discipline_ids"] = sorted(expected["discipline_ids"])
        assert data == expected

    async def test_list_werewolf_tribes(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list werewolf tribes endpoint is working."""
        response = await client.get(
            build_url(CharacterBlueprints.WEREWOLF_TRIBES, company_id=mirror_company.id),
            headers=token_company_admin,
        )
        werewolf_tribes = (
            await WerewolfTribe.filter(is_archived=False).order_by("name").prefetch_related("gifts")
        )

        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == len(werewolf_tribes)
        assert _sort_id_lists(response.json()["items"], "gift_trait_ids") == _sort_id_lists(
            [
                msgspec.json.decode(msgspec.json.encode(WerewolfTribeResponse.from_model(wt)))
                for wt in werewolf_tribes[:10]
            ],
            "gift_trait_ids",
        )

    async def test_get_werewolf_tribe(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get werewolf tribe endpoint is working."""
        werewolf_tribe = (
            await WerewolfTribe.filter(is_archived=False).prefetch_related("gifts").first()
        )
        response = await client.get(
            build_url(
                CharacterBlueprints.WEREWOLF_TRIBE_DETAIL,
                company_id=mirror_company.id,
                werewolf_tribe_id=werewolf_tribe.id,
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        data = response.json()
        expected = msgspec.json.decode(
            msgspec.json.encode(WerewolfTribeResponse.from_model(werewolf_tribe))
        )
        data["gift_trait_ids"] = sorted(data["gift_trait_ids"])
        expected["gift_trait_ids"] = sorted(expected["gift_trait_ids"])
        assert data == expected

    async def test_list_werewolf_auspices(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list werewolf auspices endpoint is working."""
        response = await client.get(
            build_url(CharacterBlueprints.WEREWOLF_AUSPICES, company_id=mirror_company.id),
            headers=token_company_admin,
        )
        werewolf_auspices = (
            await WerewolfAuspice.filter(is_archived=False)
            .order_by("name")
            .prefetch_related("gifts")
        )

        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == len(werewolf_auspices)
        assert _sort_id_lists(response.json()["items"], "gift_trait_ids") == _sort_id_lists(
            [
                msgspec.json.decode(msgspec.json.encode(WerewolfAuspiceResponse.from_model(wa)))
                for wa in werewolf_auspices[:10]
            ],
            "gift_trait_ids",
        )

    async def test_get_werewolf_auspice(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        mirror_company: Company,
        mirror_company_admin: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get werewolf auspice endpoint is working."""
        werewolf_auspice = (
            await WerewolfAuspice.filter(is_archived=False).prefetch_related("gifts").first()
        )
        response = await client.get(
            build_url(
                CharacterBlueprints.WEREWOLF_AUSPICE_DETAIL,
                company_id=mirror_company.id,
                werewolf_auspice_id=werewolf_auspice.id,
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        data = response.json()
        expected = msgspec.json.decode(
            msgspec.json.encode(WerewolfAuspiceResponse.from_model(werewolf_auspice))
        )
        data["gift_trait_ids"] = sorted(data["gift_trait_ids"])
        expected["gift_trait_ids"] = sorted(expected["gift_trait_ids"])
        assert data == expected
