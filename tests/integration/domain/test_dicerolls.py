"""Test the gameplay domain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from vapi.constants import CharacterType, RollResultType, UserRole
from vapi.db.sql_models.character_sheet import Trait
from vapi.domain.urls import DiceRolls

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from httpx import AsyncClient

    from vapi.db.sql_models.campaign import Campaign
    from vapi.db.sql_models.character import Character
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.developer import Developer
    from vapi.db.sql_models.user import User

pytestmark = pytest.mark.anyio


class TestDiceRoll:
    """Test the dice roll endpoint."""

    async def test_diceroll_list_no_results(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify listing dice rolls returns empty when none exist."""
        response = await client.get(
            build_url(DiceRolls.LIST, company_id=session_company.id),
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == {"items": [], "limit": 10, "offset": 0, "total": 0}

    async def test_diceroll_list_with_results(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        diceroll_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify listing dice rolls returns results."""
        # Given a dice roll exists
        dice_roll = await diceroll_factory(company=session_company, user=session_user)

        # When we list dice rolls
        response = await client.get(
            build_url(DiceRolls.LIST, company_id=session_company.id),
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
        )

        # Then we get results
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(dice_roll.id)

    async def test_get_diceroll(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        diceroll_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify getting a single dice roll by ID."""
        # Given a dice roll
        dice_roll = await diceroll_factory(company=session_company, user=session_user)

        # When we get it
        response = await client.get(
            build_url(
                DiceRolls.DETAIL,
                company_id=session_company.id,
                diceroll_id=dice_roll.id,
            ),
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
        )

        # Then we get the correct roll
        assert response.status_code == HTTP_200_OK
        assert response.json()["id"] == str(dice_roll.id)

    async def test_get_dice_roll_not_found(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify getting a nonexistent dice roll returns 404."""
        dice_roll_id = uuid4()
        response = await client.get(
            build_url(
                DiceRolls.DETAIL,
                company_id=session_company.id,
                diceroll_id=dice_roll_id,
            ),
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
        )
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["detail"] == f"Dice roll {dice_roll_id} not found"

    async def test_create_diceroll(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Any],
        character_trait_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify creating a dice roll with all fields."""
        # Given a character with traits
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        character_trait = await character_trait_factory(character=character)
        trait = await Trait.filter(is_archived=False).first()

        # When we create a dice roll
        response = await client.post(
            build_url(
                DiceRolls.CREATE,
                company_id=session_company.id,
            ),
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
            json={
                "difficulty": 6,
                "dice_size": 10,
                "num_dice": 6,
                "num_desperation_dice": 0,
                "character_id": str(character.id),
                "campaign_id": str(session_campaign.id),
                "comment": "Test comment",
                "trait_ids": [str(character_trait.id), str(trait.id)],
            },
        )

        # Then the dice roll is created
        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        assert data["id"] is not None
        assert data["difficulty"] == 6
        assert data["dice_size"] == 10
        assert data["num_dice"] == 6
        assert data["num_desperation_dice"] == 0
        assert data["character_id"] == str(character.id)
        assert data["campaign_id"] == str(session_campaign.id)
        assert data["user_id"] == str(session_user.id)
        assert data["company_id"] == str(session_company.id)
        assert data["comment"] == "Test comment"
        assert data["result"]["total_result_type"] in RollResultType

    async def test_dice_roll_controller_list_filter(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Any],
        diceroll_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify filtering dice rolls by user, character, and campaign."""
        # Given dice rolls with different relations
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        dice_roll_character = await diceroll_factory(
            company=session_company, user=session_user, character=character
        )
        dice_roll_campaign = await diceroll_factory(
            company=session_company, user=session_user, campaign=session_campaign
        )
        await diceroll_factory(company=session_company, user=session_user)

        base_url = build_url(DiceRolls.LIST, company_id=session_company.id)

        # When filtering by character
        response = await client.get(
            base_url,
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
            params={"characterid": str(character.id)},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["id"] == str(dice_roll_character.id)

        # When filtering by campaign
        response = await client.get(
            base_url,
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
            params={"campaignid": str(session_campaign.id)},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["id"] == str(dice_roll_campaign.id)

        # When filtering by user
        response = await client.get(
            base_url,
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
            params={"userid": str(session_user.id)},
        )
        assert response.status_code == HTTP_200_OK
        # All 3 dice rolls belong to this user
        assert response.json()["total"] == 3

    async def test_dice_roll_controller_list_filter_character_type(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Any],
        diceroll_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify filtering dice rolls by character_type returns only matching rolls."""
        # Given a player-character roll and a storyteller-character roll
        player_character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            type="PLAYER",
        )
        storyteller_character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            type="STORYTELLER",
        )
        player_roll = await diceroll_factory(
            company=session_company, user=session_user, character=player_character
        )
        await diceroll_factory(
            company=session_company, user=session_user, character=storyteller_character
        )

        # When filtering by character_type=PLAYER
        response = await client.get(
            build_url(DiceRolls.LIST, company_id=session_company.id),
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
            params={"character_type": "PLAYER"},
        )

        # Then only the player-character roll is returned
        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["id"] == str(player_roll.id)

    async def test_dice_roll_controller_list_filter_character_type_excludes_null_character(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Any],
        diceroll_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify character_type filter excludes rolls with no character attached."""
        # Given a player-character roll and a roll with no character
        player_character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            type="PLAYER",
        )
        player_roll = await diceroll_factory(
            company=session_company, user=session_user, character=player_character
        )
        await diceroll_factory(company=session_company, user=session_user, character=None)

        base_url = build_url(DiceRolls.LIST, company_id=session_company.id)

        # When filtering by character_type=PLAYER
        filtered = await client.get(
            base_url,
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
            params={"character_type": "PLAYER"},
        )

        # Then only the player-character roll is returned (null-character roll excluded)
        assert filtered.status_code == HTTP_200_OK
        assert filtered.json()["total"] == 1
        assert filtered.json()["items"][0]["id"] == str(player_roll.id)

        # When listing without the character_type filter
        unfiltered = await client.get(
            base_url,
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
        )

        # Then both rolls are returned
        assert unfiltered.status_code == HTTP_200_OK
        assert unfiltered.json()["total"] == 2

    async def test_dice_roll_controller_list_filter_character_type_composes_with_campaign(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        campaign_factory: Callable[..., Any],
        character_factory: Callable[..., Any],
        diceroll_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify character_type and campaignid filters combine with AND semantics."""
        # Given two campaigns, each with a PLAYER and a STORYTELLER character + rolls
        other_campaign = await campaign_factory(company=session_company)
        player_in_session = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            type="PLAYER",
        )
        storyteller_in_session = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            type="STORYTELLER",
        )
        player_in_other = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=other_campaign,
            type="PLAYER",
        )
        target_roll = await diceroll_factory(
            company=session_company,
            user=session_user,
            character=player_in_session,
            campaign=session_campaign,
        )
        await diceroll_factory(
            company=session_company,
            user=session_user,
            character=storyteller_in_session,
            campaign=session_campaign,
        )
        await diceroll_factory(
            company=session_company,
            user=session_user,
            character=player_in_other,
            campaign=other_campaign,
        )

        # When filtering by campaign + character_type
        response = await client.get(
            build_url(DiceRolls.LIST, company_id=session_company.id),
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
            params={
                "campaignid": str(session_campaign.id),
                "character_type": "PLAYER",
            },
        )

        # Then only the PLAYER roll in the session campaign is returned
        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["id"] == str(target_roll.id)

    async def test_player_diceroll_list_excludes_storyteller_characters(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_campaign: Campaign,
        session_user: User,
        character_factory: Callable[..., Any],
        diceroll_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify a player listing dice rolls excludes storyteller rolls but keeps null-character rolls."""
        # Given a dice roll tied to a storyteller character and a roll with no character
        st_char = await character_factory(
            company=session_company,
            campaign=session_campaign,
            type=CharacterType.STORYTELLER,
        )
        st_roll = await diceroll_factory(
            company=session_company,
            character=st_char,
            user=session_user,
        )
        null_roll = await diceroll_factory(
            company=session_company,
            user=session_user,
        )
        player_header = {"On-Behalf-Of": str(session_user.id)}

        # When the player lists dice rolls
        response = await client.get(
            build_url(DiceRolls.LIST, company_id=session_company.id),
            headers=token_global_admin | player_header,
        )

        # Then the storyteller-character roll is excluded but the null-character roll is preserved
        assert response.status_code == HTTP_200_OK
        returned_ids = {item["id"] for item in response.json()["items"]}
        assert str(st_roll.id) not in returned_ids
        assert str(null_roll.id) in returned_ids

    async def test_storyteller_diceroll_list_includes_storyteller_characters(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_campaign: Campaign,
        session_user_storyteller: User,
        character_factory: Callable[..., Any],
        diceroll_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify a storyteller listing dice rolls still sees storyteller-character rolls."""
        # Given a dice roll tied to a storyteller character
        st_char = await character_factory(
            company=session_company,
            campaign=session_campaign,
            type=CharacterType.STORYTELLER,
        )
        st_roll = await diceroll_factory(
            company=session_company,
            character=st_char,
            user=session_user_storyteller,
        )

        # When the storyteller lists dice rolls
        response = await client.get(
            build_url(DiceRolls.LIST, company_id=session_company.id),
            headers=token_global_admin | {"On-Behalf-Of": str(session_user_storyteller.id)},
        )

        # Then the storyteller-character roll is returned
        assert response.status_code == HTTP_200_OK
        returned_ids = {item["id"] for item in response.json()["items"]}
        assert str(st_roll.id) in returned_ids

    async def test_player_get_diceroll_storyteller_character_forbidden(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_campaign: Campaign,
        session_user: User,
        character_factory: Callable[..., Any],
        diceroll_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify a player cannot fetch a dice roll tied to a storyteller character."""
        # Given a dice roll tied to a storyteller character
        st_char = await character_factory(
            company=session_company,
            campaign=session_campaign,
            type=CharacterType.STORYTELLER,
        )
        st_roll = await diceroll_factory(
            company=session_company,
            character=st_char,
            user=session_user,
        )

        # When the player fetches that dice roll by ID
        response = await client.get(
            build_url(
                DiceRolls.DETAIL,
                company_id=session_company.id,
                diceroll_id=st_roll.id,
            ),
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
        )

        # Then access is denied
        assert response.status_code == HTTP_403_FORBIDDEN

    async def test_create_diceroll_from_quickroll(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Any],
        character_trait_factory: Callable[..., Any],
        quickroll_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify creating a dice roll from a quickroll."""
        # Given a character with traits matching a quickroll
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )

        # Use distinct traits for the two character traits
        distinct_traits = await Trait.filter(is_archived=False).limit(2)
        trait1, trait2 = distinct_traits[0], distinct_traits[1]
        await character_trait_factory(character=character, trait=trait1)
        await character_trait_factory(character=character, trait=trait2)

        quickroll = await quickroll_factory(
            name="Quick Roll 1",
            user=session_user,
            traits=[trait1, trait2],
        )

        # When we create a quick roll
        response = await client.post(
            build_url(
                DiceRolls.QUICKROLL,
                company_id=session_company.id,
            ),
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
            json={
                "quickroll_id": str(quickroll.id),
                "character_id": str(character.id),
                "comment": "Test comment",
            },
        )

        # Then the dice roll is created
        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        assert data["comment"] == "Test comment"
        assert data["difficulty"] == 6
        assert data["num_desperation_dice"] == 0
        assert sorted(data["trait_ids"]) == sorted([str(trait1.id), str(trait2.id)])
        assert data["character_id"] == str(character.id)
        assert data["campaign_id"] == str(session_campaign.id)
        assert data["user_id"] == str(session_user.id)
        assert data["company_id"] == str(session_company.id)
        assert data["result"]["total_result_type"] in RollResultType

    async def test_player_can_roll_dice_for_npc_when_storyteller_only(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        company_factory: Callable[..., Any],
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify dice rolls for an NPC are not gated by permission_manage_npc."""
        # Given a STORYTELLER-only company, an NPC, and a player
        company = await company_factory(settings__permission_manage_npc="STORYTELLER")
        player = await user_factory(company=company, role=UserRole.PLAYER.value)
        npc = await character_factory(company=company, type=CharacterType.NPC)

        # When the player rolls dice for the NPC
        response = await client.post(
            build_url(DiceRolls.CREATE, company_id=company.id),
            headers=token_global_admin | {"On-Behalf-Of": str(player.id)},
            json={"num_dice": 3, "difficulty": 6, "character_id": str(npc.id)},
        )

        # Then the roll succeeds (dice rolls are never gated by permission_manage_npc)
        assert response.status_code == HTTP_201_CREATED
