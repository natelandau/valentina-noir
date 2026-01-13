"""Test the gameplay domain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from beanie import PydanticObjectId
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_404_NOT_FOUND,
)

from vapi.constants import RollResultType
from vapi.db.models import QuickRoll, Trait
from vapi.domain.controllers.dicerolls.dto import QuickRollDTO
from vapi.domain.urls import DiceRolls

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.models import Campaign, Character, CharacterTrait, Company, DiceRoll, User

pytestmark = pytest.mark.anyio


class TestDiceRoll:
    """Test the dice roll endpoint."""

    async def test_diceroll_list_no_results(
        self,
        client: AsyncClient,
        token_company_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the dice roll endpoint list no results."""
        response = await client.get(build_url(DiceRolls.LIST), headers=token_company_admin)
        assert response.status_code == HTTP_200_OK
        assert response.json() == {"items": [], "limit": 10, "offset": 0, "total": 0}

    async def test_diceroll_list_with_results(
        self,
        client: AsyncClient,
        token_company_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        dice_roll_factory: Callable[[dict[str, Any]], DiceRoll],
        debug: Callable[[Any], None],
    ) -> None:
        """Test diceroll list with results."""
        dice_roll = await dice_roll_factory()
        response = await client.get(build_url(DiceRolls.LIST), headers=token_company_admin)
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "items": [dice_roll.model_dump(mode="json", exclude={"is_archived", "archive_date"})],
            "limit": 10,
            "offset": 0,
            "total": 1,
        }

    async def test_get_diceroll(
        self,
        client: AsyncClient,
        token_company_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        dice_roll_factory: Callable[[dict[str, Any]], DiceRoll],
        debug: Callable[[Any], None],
    ) -> None:
        """Test get diceroll."""
        dice_roll = await dice_roll_factory()
        response = await client.get(
            build_url(DiceRolls.DETAIL, diceroll_id=dice_roll.id), headers=token_company_admin
        )
        assert response.status_code == HTTP_200_OK
        response_json = response.json()
        assert response_json == dice_roll.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )

    async def test_get_dice_roll_not_found(
        self,
        client: AsyncClient,
        token_company_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the dice roll controller get not found."""
        dice_roll_id = PydanticObjectId()
        response = await client.get(
            build_url(DiceRolls.DETAIL, diceroll_id=dice_roll_id), headers=token_company_admin
        )
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["detail"] == f"Dice roll {dice_roll_id} not found"

    async def test_create_diceroll(
        self,
        client: AsyncClient,
        token_company_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        base_company: Company,
        base_user: User,
        base_character: Character,
        base_campaign: Campaign,
        debug: Callable[[Any], None],
        character_trait_factory: Callable[[dict[str, Any]], CharacterTrait],
    ) -> None:
        """Test the dice roll controller with character traits."""
        character_trait = await character_trait_factory()
        trait = await Trait.find_one(Trait.is_archived == False)

        response = await client.post(
            build_url(DiceRolls.CREATE),
            headers=token_company_admin,
            json={
                "difficulty": 6,
                "dice_size": 10,
                "num_dice": 6,
                "num_desperation_dice": 0,
                "character_id": str(base_character.id),
                "campaign_id": str(base_campaign.id),
                "comment": "Test comment",
                "trait_ids": [str(character_trait.id), str(trait.id)],
            },
        )
        assert response.status_code == HTTP_201_CREATED
        assert response.json()["id"] is not None
        assert response.json()["trait_ids"] == [str(character_trait.trait.id), str(trait.id)]
        assert response.json()["difficulty"] == 6
        assert response.json()["dice_size"] == 10
        assert response.json()["num_dice"] == 6
        assert response.json()["num_desperation_dice"] == 0
        assert response.json()["character_id"] == str(base_character.id)
        assert response.json()["campaign_id"] == str(base_campaign.id)
        assert response.json()["user_id"] == str(base_user.id)
        assert response.json()["company_id"] == str(base_company.id)
        assert response.json()["comment"] == "Test comment"
        assert response.json()["result"]["total_result_type"] in RollResultType

    async def test_dice_roll_controller_list_filter(
        self,
        client: AsyncClient,
        token_company_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        base_user: User,
        base_character: Character,
        base_campaign: Campaign,
        debug: Callable[[Any], None],
        dice_roll_factory: Callable[[dict[str, Any]], DiceRoll],
    ) -> None:
        """Test the dice roll controller list filter."""
        dice_roll_character = await dice_roll_factory(character_id=base_character.id)
        dice_roll_campaign = await dice_roll_factory(campaign_id=base_campaign.id)
        dice_roll_user = await dice_roll_factory(user_id=base_user.id)

        response = await client.get(
            build_url(DiceRolls.LIST),
            headers=token_company_admin,
            params={"characterid": str(base_character.id)},
        )
        assert response.status_code == HTTP_200_OK
        response_json = response.json()
        assert response_json["items"] == [
            dice_roll_character.model_dump(mode="json", exclude={"is_archived", "archive_date"}),
        ]
        assert response_json["limit"] == 10
        assert response_json["offset"] == 0
        assert response_json["total"] == 1

        response = await client.get(
            build_url(DiceRolls.LIST),
            headers=token_company_admin,
            params={"campaignid": str(base_campaign.id)},
        )
        assert response.status_code == HTTP_200_OK
        response_json = response.json()
        assert response_json["items"] == [
            dice_roll_campaign.model_dump(mode="json", exclude={"is_archived", "archive_date"}),
        ]
        assert response_json["limit"] == 10
        assert response_json["offset"] == 0
        assert response_json["total"] == 1

        response = await client.get(
            build_url(DiceRolls.LIST),
            headers=token_company_admin,
            params={"userid": str(base_user.id)},
        )
        assert response.status_code == HTTP_200_OK
        response_json = response.json()
        assert response_json["items"] == [
            dice_roll_user.model_dump(mode="json", exclude={"is_archived", "archive_date"}),
        ]
        assert response_json["limit"] == 10
        assert response_json["offset"] == 0
        assert response_json["total"] == 1

    async def test_create_diceroll_from_quickroll(
        self,
        client: AsyncClient,
        token_company_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        base_company: Company,
        base_user: User,
        base_character: Character,
        base_campaign: Campaign,
        character_trait_factory: Callable[[dict[str, Any]], CharacterTrait],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the create diceroll from quickroll endpoint."""
        character_trait1 = await character_trait_factory()
        character_trait2 = await character_trait_factory()
        quickroll = QuickRoll(
            name="Quick Roll 1",
            user_id=base_user.id,
            trait_ids=[character_trait1.trait.id, character_trait2.trait.id],
        )
        await quickroll.save()

        quickroll_dto = QuickRollDTO(
            quickroll_id=quickroll.id,
            character_id=base_character.id,
            comment="Test comment",
        )

        # When we create a quick roll
        response = await client.post(
            build_url(DiceRolls.QUICKROLL),
            headers=token_company_admin,
            json=quickroll_dto.model_dump(mode="json"),
        )
        assert response.status_code == HTTP_201_CREATED
        response_json = response.json()
        assert response_json["comment"] == "Test comment"
        assert response_json["difficulty"] == 6
        assert response_json["num_desperation_dice"] == 0
        assert response_json["trait_ids"] == [
            str(character_trait1.trait.id),
            str(character_trait2.trait.id),
        ]
        assert response_json["character_id"] == str(base_character.id)
        assert response_json["campaign_id"] == str(base_campaign.id)
        assert response_json["user_id"] == str(base_user.id)
        assert response_json["company_id"] == str(base_company.id)
        assert response_json["result"]["total_result_type"] in RollResultType
