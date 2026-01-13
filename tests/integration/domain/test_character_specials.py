"""Test character specials controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
)

from vapi.db.models import (
    Character,
    HunterEdge,
    HunterEdgePerk,
    WerewolfAuspice,
    WerewolfGift,
    WerewolfRite,
    WerewolfTribe,
)
from vapi.db.models.character import HunterAttributesEdgeModel, WerewolfAttributes
from vapi.domain.controllers.character_specials.dto import CharacterEdgeAndPerksDTO
from vapi.domain.urls import Characters

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient


pytestmark = pytest.mark.anyio


@pytest.fixture
async def get_mock_hunter_data(
    character_factory: Callable[[dict[str, Any]], Character],
) -> tuple[Character, CharacterEdgeAndPerksDTO]:
    """Get mock data for hunter edge and perks."""
    character = await character_factory(character_class="HUNTER")
    hunter_edge = await HunterEdge.find_one(HunterEdge.is_archived == False)
    hunter_edge_perks = (
        await HunterEdgePerk.find(
            HunterEdgePerk.is_archived == False, HunterEdgePerk.edge_id == hunter_edge.id
        )
        .limit(2)
        .to_list()
    )

    character_edge = HunterAttributesEdgeModel(
        edge_id=hunter_edge.id,
        perk_ids=[hunter_edge_perk.id for hunter_edge_perk in hunter_edge_perks],
    )

    character.hunter_attributes.edges = [character_edge]
    character.hunter_attributes.creed = "Creed"
    await character.save()

    character_edge_dto = CharacterEdgeAndPerksDTO(
        id=hunter_edge.id,
        name=hunter_edge.name,
        pool=hunter_edge.pool,
        system=hunter_edge.system,
        type=hunter_edge.type,
        description=hunter_edge.description,
        perks=[hunter_edge_perk.model_dump(mode="json") for hunter_edge_perk in hunter_edge_perks],
    )

    return character, character_edge_dto


@pytest.fixture
async def werewolf_character(
    character_factory: Callable[[dict[str, Any]], Character],
) -> Character:
    """Get mock data for werewolf gifts and rites."""
    character = await character_factory(character_class="WEREWOLF")
    tribe = await WerewolfTribe.find_one(WerewolfTribe.is_archived == False)
    auspice = await WerewolfAuspice.find_one(WerewolfAuspice.is_archived == False)
    gift = await WerewolfGift.find_one(WerewolfGift.is_archived == False)
    rite = await WerewolfRite.find_one(WerewolfRite.is_archived == False)

    character.werewolf_attributes = WerewolfAttributes(
        tribe_id=tribe.id,
        tribe_name=tribe.name,
        auspice_id=auspice.id,
        auspice_name=auspice.name,
        gift_ids=[gift.id],
        rite_ids=[rite.id],
        total_renown=10,
    )
    await character.save()
    yield character
    await character.delete()


class TestHunterSpecialsController:
    """Test hunter edge controller."""

    async def test_list_hunter_edges_no_edges(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
    ) -> None:
        """Test list hunter edges."""
        response = await client.get(build_url(Characters.EDGES), headers=token_company_admin)
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == []
        assert response.json()["total"] == 0
        assert response.json()["limit"] == 10
        assert response.json()["offset"] == 0

    async def test_list_hunter_edges_with_edges(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        get_mock_hunter_data: Callable[[], tuple[Character, CharacterEdgeAndPerksDTO]],
    ) -> None:
        """Test list hunter edges."""
        # Given a character with hunter attributes
        character, character_edge_dto = get_mock_hunter_data

        # When we list the hunter edges
        response = await client.get(
            build_url(Characters.EDGES, character_id=character.id), headers=token_company_admin
        )

        # Then verify the response is correct
        assert response.status_code == HTTP_200_OK

        assert response.json()["total"] == 1
        assert response.json()["limit"] == 10
        assert response.json()["offset"] == 0

        assert response.json()["items"] == [character_edge_dto.model_dump(mode="json")]

    async def test_get_hunter_edge(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        get_mock_hunter_data: Callable[[], tuple[Character, CharacterEdgeAndPerksDTO]],
    ) -> None:
        """Test list hunter edges."""
        # Given a character with hunter attributes
        character, character_edge_dto = get_mock_hunter_data

        # When we get the hunter edge
        response = await client.get(
            build_url(
                Characters.EDGE_DETAIL,
                character_id=character.id,
                hunter_edge_id=character_edge_dto.id,
            ),
            headers=token_company_admin,
        )

        # Then verify the response is correct
        assert response.status_code == HTTP_200_OK

        assert response.json() == character_edge_dto.model_dump(mode="json")

    async def test_list_hunter_edge_perks(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        get_mock_hunter_data: Callable[[], tuple[Character, CharacterEdgeAndPerksDTO]],
    ) -> None:
        """Test list hunter edge perks."""
        character, character_edge_dto = get_mock_hunter_data
        response = await client.get(
            build_url(
                Characters.EDGE_PERKS,
                character_id=character.id,
                hunter_edge_id=character_edge_dto.id,
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == len(character_edge_dto.perks)
        assert response.json()["items"] == [
            perk.model_dump(mode="json") for perk in character_edge_dto.perks
        ]
        assert response.json()["limit"] == 10
        assert response.json()["offset"] == 0

    async def test_get_hunter_edge_perk(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        get_mock_hunter_data: Callable[[], tuple[Character, CharacterEdgeAndPerksDTO]],
    ) -> None:
        """Test get hunter edge perk."""
        character, character_edge_dto = get_mock_hunter_data
        response = await client.get(
            build_url(
                Characters.EDGE_PERK_DETAIL,
                character_id=character.id,
                hunter_edge_id=character_edge_dto.id,
                hunter_edge_perk_id=character_edge_dto.perks[0].id,
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == character_edge_dto.perks[0].model_dump(mode="json")

    async def test_add_hunter_edge(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        get_mock_hunter_data: Callable[[], tuple[Character, CharacterEdgeAndPerksDTO]],
    ) -> None:
        """Test add hunter edge."""
        character, character_edge_dto = get_mock_hunter_data
        new_hunter_edge = await HunterEdge.find_one(
            HunterEdge.is_archived == False, HunterEdge.id != character_edge_dto.id
        )

        # When we add the hunter edge
        response = await client.post(
            build_url(
                Characters.EDGE_ADD,
                character_id=character.id,
                hunter_edge_id=str(new_hunter_edge.id),
            ),
            headers=token_company_admin,
        )

        # Then verify the response is correct
        assert response.status_code == HTTP_201_CREATED

        assert response.json() == {
            "id": str(new_hunter_edge.id),
            "name": new_hunter_edge.name,
            "pool": new_hunter_edge.pool,
            "system": new_hunter_edge.system,
            "type": new_hunter_edge.type.value,
            "description": new_hunter_edge.description,
            "perks": [],
        }

        await character.sync()
        assert character.hunter_attributes.edges == [
            HunterAttributesEdgeModel(
                edge_id=character_edge_dto.id,
                perk_ids=[perk.id for perk in character_edge_dto.perks],
            ),
            HunterAttributesEdgeModel(edge_id=new_hunter_edge.id, perk_ids=[]),
        ]
        assert character.hunter_attributes.creed == "Creed"

    async def test_remove_hunter_edge(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        get_mock_hunter_data: Callable[[], tuple[Character, CharacterEdgeAndPerksDTO]],
    ) -> None:
        """Test remove hunter edge."""
        character, character_edge_dto = get_mock_hunter_data
        response = await client.delete(
            build_url(
                Characters.EDGE_REMOVE,
                character_id=character.id,
                hunter_edge_id=str(character_edge_dto.id),
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_204_NO_CONTENT

        await character.sync()
        assert character.hunter_attributes.edges == []
        assert character.hunter_attributes.creed == "Creed"

    async def test_add_perk_to_edge(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        get_mock_hunter_data: Callable[[], tuple[Character, CharacterEdgeAndPerksDTO]],
    ) -> None:
        """Test add perk to edge."""
        character, character_edge_dto = get_mock_hunter_data
        new_edge = await HunterEdge.find_one(
            HunterEdge.is_archived == False, HunterEdge.id != character_edge_dto.id
        )
        new_perk = await HunterEdgePerk.find_one(
            HunterEdgePerk.is_archived == False, HunterEdgePerk.edge_id == new_edge.id
        )

        # When we add the perk to the edge
        response = await client.post(
            build_url(
                Characters.EDGE_PERK_ADD,
                character_id=character.id,
                hunter_edge_id=str(new_perk.edge_id),
                hunter_edge_perk_id=str(new_perk.id),
            ),
            headers=token_company_admin,
        )
        # debug(response.json())

        # Then verify the response is correct
        assert response.status_code == HTTP_201_CREATED
        assert response.json() == {
            "id": str(new_edge.id),
            "name": new_edge.name,
            "description": new_edge.description,
            "pool": new_edge.pool,
            "system": new_edge.system,
            "type": new_edge.type.value,
            "perks": [
                {
                    "id": str(new_perk.id),
                    "name": new_perk.name,
                    "description": new_perk.description,
                }
            ],
        }

        await character.sync()
        # debug(character.hunter_attributes.edges)
        assert character.hunter_attributes.edges == [
            HunterAttributesEdgeModel(
                edge_id=character_edge_dto.id,
                perk_ids=[perk.id for perk in character_edge_dto.perks],
            ),
            HunterAttributesEdgeModel(edge_id=new_edge.id, perk_ids=[new_perk.id]),
        ]
        assert character.hunter_attributes.creed == "Creed"

    async def test_remove_perk_from_edge(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        get_mock_hunter_data: Callable[[], tuple[Character, CharacterEdgeAndPerksDTO]],
    ) -> None:
        """Test remove perk from edge."""
        character, character_edge_dto = get_mock_hunter_data
        response = await client.delete(
            build_url(
                Characters.EDGE_PERK_REMOVE,
                character_id=character.id,
                hunter_edge_id=str(character_edge_dto.id),
                hunter_edge_perk_id=str(character_edge_dto.perks[0].id),
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_204_NO_CONTENT

        await character.sync()
        assert character.hunter_attributes.edges == [
            HunterAttributesEdgeModel(
                edge_id=character_edge_dto.id,
                perk_ids=[
                    perk.id
                    for perk in character_edge_dto.perks
                    if perk.id != character_edge_dto.perks[0].id
                ],
            ),
        ]
        assert character.hunter_attributes.creed == "Creed"


class TestWerewolfSpecialsController:
    """Test werewolf specials controller."""

    async def test_list_werewolf_gifts(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test list werewolf gifts."""
        gift = await WerewolfGift.get(werewolf_character.werewolf_attributes.gift_ids[0])
        response = await client.get(
            build_url(Characters.GIFTS, character_id=werewolf_character.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == 1
        assert response.json()["items"] == [
            gift.model_dump(mode="json", exclude={"is_archived", "archive_date"})
        ]
        assert response.json()["limit"] == 10
        assert response.json()["offset"] == 0

    async def test_get_werewolf_gift(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test get werewolf gift."""
        gift = await WerewolfGift.get(werewolf_character.werewolf_attributes.gift_ids[0])
        response = await client.get(
            build_url(
                Characters.GIFT_DETAIL, character_id=werewolf_character.id, werewolf_gift_id=gift.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == gift.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )

    async def test_add_werewolf_gift(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test add werewolf gift."""
        gift = await WerewolfGift.find_one(
            WerewolfGift.is_archived == False,
            WerewolfGift.id != werewolf_character.werewolf_attributes.gift_ids[0],
        )
        response = await client.post(
            build_url(
                Characters.GIFT_ADD, character_id=werewolf_character.id, werewolf_gift_id=gift.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_201_CREATED
        assert response.json() == gift.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )
        await werewolf_character.sync()
        assert werewolf_character.werewolf_attributes.gift_ids == [
            werewolf_character.werewolf_attributes.gift_ids[0],
            gift.id,
        ]
        assert werewolf_character.werewolf_attributes.total_renown == 10
        assert werewolf_character.werewolf_attributes.tribe_id is not None

    async def test_remove_werewolf_gift(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test remove werewolf gift."""
        gift = await WerewolfGift.get(werewolf_character.werewolf_attributes.gift_ids[0])
        response = await client.delete(
            build_url(
                Characters.GIFT_REMOVE, character_id=werewolf_character.id, werewolf_gift_id=gift.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_204_NO_CONTENT
        await werewolf_character.sync()
        assert werewolf_character.werewolf_attributes.gift_ids == []
        assert werewolf_character.werewolf_attributes.total_renown == 10
        assert werewolf_character.werewolf_attributes.tribe_id is not None


class TestWerewolfRitesController:
    """Test werewolf rites controller."""

    async def test_list_werewolf_rites(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test list werewolf rites."""
        rite = await WerewolfRite.get(werewolf_character.werewolf_attributes.rite_ids[0])
        response = await client.get(
            build_url(Characters.RITES, character_id=werewolf_character.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == 1
        assert response.json()["items"] == [
            rite.model_dump(mode="json", exclude={"is_archived", "archive_date"})
        ]
        assert response.json()["limit"] == 10
        assert response.json()["offset"] == 0

    async def test_get_werewolf_rite(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test get werewolf rite."""
        rite = await WerewolfRite.get(werewolf_character.werewolf_attributes.rite_ids[0])
        response = await client.get(
            build_url(
                Characters.RITE_DETAIL, character_id=werewolf_character.id, werewolf_rite_id=rite.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == rite.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )

    async def test_add_werewolf_rite(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test add werewolf rite."""
        rite = await WerewolfRite.find_one(
            WerewolfRite.is_archived == False,
            WerewolfRite.id != werewolf_character.werewolf_attributes.rite_ids[0],
        )
        response = await client.post(
            build_url(
                Characters.RITE_ADD, character_id=werewolf_character.id, werewolf_rite_id=rite.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_201_CREATED
        assert response.json() == rite.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )
        await werewolf_character.sync()
        assert werewolf_character.werewolf_attributes.rite_ids == [
            werewolf_character.werewolf_attributes.rite_ids[0],
            rite.id,
        ]
        assert werewolf_character.werewolf_attributes.total_renown == 10

    async def test_remove_werewolf_rite(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test remove werewolf rite."""
        rite = await WerewolfRite.get(werewolf_character.werewolf_attributes.rite_ids[0])
        response = await client.delete(
            build_url(
                Characters.RITE_REMOVE, character_id=werewolf_character.id, werewolf_rite_id=rite.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_204_NO_CONTENT
        await werewolf_character.sync()
        assert werewolf_character.werewolf_attributes.rite_ids == []
        assert werewolf_character.werewolf_attributes.total_renown == 10
        assert werewolf_character.werewolf_attributes.tribe_id is not None
