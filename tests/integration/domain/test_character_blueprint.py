"""Test sheet section controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
)

from vapi.constants import CharacterClass, GameVersion, HunterEdgeType
from vapi.db.models import (
    CharacterConcept,
    CharSheetSection,
    HunterEdge,
    HunterEdgePerk,
    Trait,
    TraitCategory,
    VampireClan,
    WerewolfAuspice,
    WerewolfGift,
    WerewolfRite,
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
            build_url(CharacterBlueprints.SECTIONS, game_version=GameVersion.V4.name),
            headers=token_company_admin,
            params={"character_class": CharacterClass.VAMPIRE.name},
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
                game_version=GameVersion.V4.name,
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
                section_id=sheet_section.id,
                game_version=GameVersion.V4.name,
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
            build_url(
                CharacterBlueprints.CATEGORIES,
                section_id=sheet_section.id,
                game_version=GameVersion.V4.name,
            ),
            headers=token_company_admin,
            params={"character_class": CharacterClass.VAMPIRE.name},
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
                game_version=GameVersion.V4.name,
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

    async def test_list_sheet_traits(
        self,
        *,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list sheet traits endpoint is working."""
        trait_category = await TraitCategory.find_one(
            TraitCategory.is_archived == False,
        )
        category_traits = await Trait.find(
            Trait.is_archived == False,
            Trait.parent_category_id == trait_category.id,
            Trait.game_versions == GameVersion.V4,
            Trait.character_classes == CharacterClass.VAMPIRE,
            Trait.custom_for_character_id == None,
        ).to_list()
        # character = await character_factory()
        response = await client.get(
            build_url(
                CharacterBlueprints.CATEGORY_TRAITS,
                category_id=trait_category.id,
                section_id=trait_category.parent_sheet_section_id,
                game_version=GameVersion.V4.name,
            ),
            headers=token_company_admin,
            params={"character_class": CharacterClass.VAMPIRE.name},
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert len(response.json()["items"]) == len(category_traits)
        assert response.json()["items"] == [
            trait.model_dump(mode="json", exclude={"is_archived", "archive_date"})
            for trait in category_traits
        ]


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
                exclude={
                    "is_archived",
                    "archive_date",
                    "company_id",
                    "date_created",
                    "date_modified",
                },
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
            exclude={"is_archived", "archive_date", "company_id", "date_created", "date_modified"},
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
                CharacterBlueprints.WEREWOLF_AUSPIE_DETAIL, werewolf_auspice_id=werewolf_auspice.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json() == werewolf_auspice.model_dump(
            mode="json",
            exclude={"is_archived", "archive_date"},
        )

    async def test_list_werewolf_gifts(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list werewolf gifts endpoint is working."""
        response = await client.get(
            build_url(CharacterBlueprints.WEREWOLF_GIFTS),
            headers=token_company_admin,
        )
        werewolf_gifts = (
            await WerewolfGift.find(WerewolfGift.is_archived == False).sort("name").to_list()
        )

        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json()["total"] == len(werewolf_gifts)
        assert response.json()["items"] == [
            werewolf_gift.model_dump(
                mode="json",
                exclude={"is_archived", "archive_date"},
            )
            for werewolf_gift in werewolf_gifts[:10]
        ]

    async def test_get_werewolf_gift(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get werewolf gift endpoint is working."""
        werewolf_gift = await WerewolfGift.find_one(WerewolfGift.is_archived == False)
        response = await client.get(
            build_url(CharacterBlueprints.WEREWOLF_GIFT_DETAIL, werewolf_gift_id=werewolf_gift.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json() == werewolf_gift.model_dump(
            mode="json",
            exclude={"is_archived", "archive_date"},
        )

    async def test_list_werewolf_gifts_by_tribe(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list werewolf gifts by tribe endpoint is working."""
        tribe = await WerewolfTribe.find_one(WerewolfTribe.is_archived == False)
        response = await client.get(
            build_url(CharacterBlueprints.WEREWOLF_GIFTS),
            headers=token_company_admin,
            params={"tribe_id": tribe.id},
        )
        werewolf_gifts = (
            await WerewolfGift.find(
                WerewolfGift.is_archived == False, WerewolfGift.tribe_id == tribe.id
            )
            .sort("name")
            .to_list()
        )

        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json()["total"] == len(werewolf_gifts)
        assert response.json()["items"] == [
            werewolf_gift.model_dump(
                mode="json",
                exclude={"is_archived", "archive_date"},
            )
            for werewolf_gift in werewolf_gifts[:10]
        ]

    async def test_list_werewolf_gifts_by_auspice(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list werewolf gifts by auspice endpoint is working."""
        auspice = await WerewolfAuspice.find_one(WerewolfAuspice.is_archived == False)
        response = await client.get(
            build_url(CharacterBlueprints.WEREWOLF_GIFTS),
            headers=token_company_admin,
            params={"auspice_id": auspice.id},
        )
        werewolf_gifts = (
            await WerewolfGift.find(
                WerewolfGift.is_archived == False, WerewolfGift.auspice_id == auspice.id
            )
            .sort("name")
            .to_list()
        )

        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json()["total"] == len(werewolf_gifts)
        assert response.json()["items"] == [
            werewolf_gift.model_dump(
                mode="json",
                exclude={"is_archived", "archive_date"},
            )
            for werewolf_gift in werewolf_gifts[:10]
        ]

    async def test_list_werewolf_rites(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list werewolf rites endpoint is working."""
        response = await client.get(
            build_url(CharacterBlueprints.WEREWOLF_RITES),
            headers=token_company_admin,
        )
        werewolf_rites = (
            await WerewolfRite.find(WerewolfRite.is_archived == False).sort("name").to_list()
        )

        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json()["total"] == len(werewolf_rites)
        assert response.json()["items"] == [
            werewolf_rite.model_dump(
                mode="json",
                exclude={"is_archived", "archive_date"},
            )
            for werewolf_rite in werewolf_rites[:10]
        ]

    async def test_get_werewolf_rite(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get werewolf rite endpoint is working."""
        werewolf_rite = await WerewolfRite.find_one(WerewolfRite.is_archived == False)
        response = await client.get(
            build_url(CharacterBlueprints.WEREWOLF_RITE_DETAIL, werewolf_rite_id=werewolf_rite.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json() == werewolf_rite.model_dump(
            mode="json",
            exclude={"is_archived", "archive_date"},
        )

    async def test_list_hunter_edges(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list hunter edges endpoint is working."""
        response = await client.get(
            build_url(CharacterBlueprints.HUNTER_EDGES),
            headers=token_company_admin,
        )
        hunter_edges = await HunterEdge.find(HunterEdge.is_archived == False).sort("name").to_list()
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json()["total"] == len(hunter_edges)
        assert response.json()["items"] == [
            hunter_edge.model_dump(
                mode="json",
                exclude={"is_archived", "archive_date"},
            )
            for hunter_edge in hunter_edges[:10]
        ]

    async def test_list_hunter_edges_by_type(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list hunter edges by type endpoint is working."""
        response = await client.get(
            build_url(CharacterBlueprints.HUNTER_EDGES),
            headers=token_company_admin,
            params={"edge_type": HunterEdgeType.ASSETS.name},
        )
        hunter_edges = (
            await HunterEdge.find(
                HunterEdge.is_archived == False,
                HunterEdge.type == HunterEdgeType.ASSETS,
            )
            .sort("name")
            .to_list()
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json()["total"] == len(hunter_edges)
        assert response.json()["items"] == [
            hunter_edge.model_dump(
                mode="json",
                exclude={"is_archived", "archive_date"},
            )
            for hunter_edge in hunter_edges[:10]
        ]

    async def test_get_hunter_edge(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get hunter edge endpoint is working."""
        hunter_edge = await HunterEdge.find_one(HunterEdge.is_archived == False)
        response = await client.get(
            build_url(CharacterBlueprints.HUNTER_EDGE_DETAIL, hunter_edge_id=hunter_edge.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json() == hunter_edge.model_dump(
            mode="json",
            exclude={"is_archived", "archive_date"},
        )

    async def test_list_hunter_edge_perks(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the list hunter edge perks endpoint is working."""
        hunter_edge = await HunterEdge.find_one(HunterEdge.is_archived == False)
        response = await client.get(
            build_url(CharacterBlueprints.HUNTER_EDGE_PERKS, hunter_edge_id=hunter_edge.id),
            headers=token_company_admin,
        )
        hunter_edge_perks = (
            await HunterEdgePerk.find(
                HunterEdgePerk.is_archived == False, HunterEdgePerk.edge_id == hunter_edge.id
            )
            .sort("name")
            .to_list()
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json()["total"] == len(hunter_edge_perks)
        assert response.json()["items"] == [
            hunter_edge_perk.model_dump(
                mode="json",
                exclude={"is_archived", "archive_date"},
            )
            for hunter_edge_perk in hunter_edge_perks[:10]
        ]

    async def test_get_hunter_edge_perk(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the get hunter edge perk endpoint is working."""
        hunter_edge_perk = await HunterEdgePerk.find_one(HunterEdgePerk.is_archived == False)
        response = await client.get(
            build_url(
                CharacterBlueprints.HUNTER_EDGE_PERK_DETAIL,
                hunter_edge_id=hunter_edge_perk.edge_id,
                hunter_edge_perk_id=hunter_edge_perk.id,
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
        assert response.json() == hunter_edge_perk.model_dump(
            mode="json",
            exclude={"is_archived", "archive_date"},
        )
