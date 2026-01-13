"""Test character generation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import ANY

import pytest
from beanie import PydanticObjectId
from litestar.status_codes import (
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
)

from vapi.constants import CharacterClass, CharacterType
from vapi.db.models import (
    Character,
    CharacterConcept,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)
from vapi.domain.handlers.character_autogeneration.constants import (
    AbilityFocus,
    AutoGenExperienceLevel,
)
from vapi.domain.services import GetModelByIdValidationService
from vapi.domain.urls import Characters as CharacterURL

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.models import Campaign, Company, User

pytestmark = pytest.mark.anyio

EXCLUDE_CHARACTER_FIELDS = {
    "archive_date",
    "is_archived",
    "is_temporary",
    "is_chargen",
    "chargen_session_id",
}


class TestAutogenerateCharacter:
    """Test autogenerate character endpoints."""

    async def test_autogenerate_must_be_storyteller(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        debug: Callable[[Any], None],
    ) -> None:
        """Test autogenerate character must be storyteller."""
        response = await client.post(
            build_url(CharacterURL.AUTOGENERATE),
            headers=token_company_admin,
            json={"character_type": CharacterType.PLAYER.name},
        )
        assert response.status_code == HTTP_403_FORBIDDEN

    async def test_autogenerate_character(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user_storyteller: User,
        base_campaign: Campaign,
        debug: Callable[[Any], None],
        mocker: Any,
    ) -> None:
        """Test autogenerate character endpoint."""
        concept = await CharacterConcept.find_one(CharacterConcept.is_archived == False)
        clan = await VampireClan.find_one(
            VampireClan.is_archived == False, VampireClan.game_versions == "V5"
        )
        tribe = await WerewolfTribe.find_one(WerewolfTribe.is_archived == False)
        auspice = await WerewolfAuspice.find_one(WerewolfAuspice.is_archived == False)
        spy1 = mocker.spy(GetModelByIdValidationService, "get_concept_by_id")
        spy2 = mocker.spy(GetModelByIdValidationService, "get_vampire_clan_by_id")
        spy3 = mocker.spy(GetModelByIdValidationService, "get_werewolf_tribe_by_id")
        spy4 = mocker.spy(GetModelByIdValidationService, "get_werewolf_auspice_by_id")

        # When creating a character with all random data
        response = await client.post(
            build_url(CharacterURL.AUTOGENERATE, user_id=str(base_user_storyteller.id)),
            headers=token_company_admin,
            json={
                "character_type": CharacterType.PLAYER.name,
                "character_class": CharacterClass.MORTAL.name,
                "concept_id": str(concept.id),
                "vampire_clan_id": str(clan.id),
                "experience_level": AutoGenExperienceLevel.NEW.name,
                "skill_focus": AbilityFocus.BALANCED.name,
                "werewolf_tribe_id": str(tribe.id),
                "werewolf_auspice_id": str(auspice.id),
            },
        )

        spy1.assert_any_call(ANY, concept.id)
        spy2.assert_any_call(ANY, clan.id)
        spy3.assert_any_call(ANY, tribe.id)
        spy4.assert_any_call(ANY, auspice.id)

        # debug(response.json())

        # Then verify the character was created successfully
        assert response.status_code == HTTP_201_CREATED
        character_id = response.json()["id"]
        character = await Character.get(character_id)
        assert character is not None
        assert character.company_id == base_company.id
        assert character.user_creator_id == base_user_storyteller.id
        assert character.user_player_id == base_user_storyteller.id
        assert character.campaign_id == base_campaign.id
        assert character.type == CharacterType.PLAYER
        assert character.character_class == CharacterClass.MORTAL
        assert character.concept_id == concept.id

        # Cleanup
        await character.delete()


class TestCharacterChargen:
    """Test character chargen endpoints."""

    @pytest.mark.parametrize(
        ("character_autogen_num_choices"),
        [
            (1),
            (3),
        ],
    )
    async def test_start_chargen_with_character_autogen_num_choices(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        character_autogen_num_choices: int,
        debug: Callable[[Any], None],
    ) -> None:
        """Test start chargen endpoint."""
        # given a company and user with the correct settings
        base_company.settings.character_autogen_num_choices = character_autogen_num_choices
        await base_company.save()

        await base_user.add_xp(base_campaign.id, 100)

        # when we start chargen
        response = await client.post(
            build_url(CharacterURL.CHARGEN_START),
            headers=token_company_admin,
        )
        # debug(response.json())

        # then we should get a 201 created response and the characters should be temporary and have the correct chargen session id
        assert response.status_code == HTTP_201_CREATED
        assert response.json()["requires_selection"] == (character_autogen_num_choices > 1)

        chargen_session_id = response.json()["session_id"]

        characters = response.json()["characters"]
        assert len(characters) == character_autogen_num_choices
        for character in characters:
            assert character["chargen_session_id"] == chargen_session_id
            assert character["is_temporary"] == (character_autogen_num_choices > 1)
            assert character["is_chargen"] is True
            assert character["is_archived"] is False

        # Cleanup
        for character_id in [character["id"] for character in characters]:
            c = await Character.get(character_id)
            if c:
                await c.delete()

    async def test_start_chargen_without_xp_cost(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
    ) -> None:
        """Test start chargen endpoint with no XP."""
        # given a company with character_autogen_num_choices set to 1
        base_company.settings.character_autogen_num_choices = 1
        base_company.settings.character_autogen_xp_cost = 100
        await base_company.save()
        # Clear the users' xp
        base_user.campaign_experience = []
        await base_user.save()

        # when we start chargen
        response = await client.post(
            build_url(CharacterURL.CHARGEN_START),
            headers=token_company_admin,
        )
        # debug(response.json())

        # then we should get a 400 bad request response
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "User does not have enough XP to complete the action."

    async def test_finalize_chargen(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
    ) -> None:
        # given a chargen session with 3 characters
        base_company.settings.character_autogen_num_choices = 3
        await base_company.save()
        await base_user.add_xp(base_campaign.id, 100)
        response = await client.post(
            build_url(CharacterURL.CHARGEN_START),
            headers=token_company_admin,
        )
        chargen_session_id = response.json()["session_id"]
        characters = response.json()["characters"]
        assert len(characters) == 3
        selected_character_id = characters[0]["id"]

        # when we finalize the chargen
        response = await client.post(
            build_url(CharacterURL.CHARGEN_FINALIZE),
            headers=token_company_admin,
            json={"session_id": chargen_session_id, "selected_character_id": selected_character_id},
        )
        # debug(response.json())

        # then we should return the selected character and delete the other characters
        assert response.status_code == HTTP_201_CREATED
        assert response.json()["id"] == selected_character_id

        for character_id in [character["id"] for character in characters]:
            c = await Character.get(character_id)
            if character_id != selected_character_id:
                assert c is None
            else:
                assert c is not None
                assert c.is_temporary is False
                assert c.is_chargen is True
                assert c.is_archived is False
                assert c.chargen_session_id is None

    async def test_finalize_chargen_invalid_session_id(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
    ) -> None:
        """Test finalize chargen endpoint with invalid session id."""
        # given a chargen session with 3 characters
        base_company.settings.character_autogen_num_choices = 3
        await base_company.save()
        await base_user.add_xp(base_campaign.id, 100)
        response = await client.post(
            build_url(CharacterURL.CHARGEN_START),
            headers=token_company_admin,
        )
        characters = response.json()["characters"]
        assert len(characters) == 3
        selected_character_id = characters[0]["id"]

        # when we finalize the chargen with an invalid session id
        response = await client.post(
            build_url(CharacterURL.CHARGEN_FINALIZE),
            headers=token_company_admin,
            json={
                "session_id": "invalid-session-id",
                "selected_character_id": selected_character_id,
            },
        )
        # debug(response.json())

        # then we should get a 400 bad request response
        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_finalize_chargen_invalid_selected_character_id(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
    ) -> None:
        # given a chargen session with 3 characters
        base_company.settings.character_autogen_num_choices = 3
        await base_company.save()
        await base_user.add_xp(base_campaign.id, 100)
        response = await client.post(
            build_url(CharacterURL.CHARGEN_START),
            headers=token_company_admin,
        )
        chargen_session_id = response.json()["session_id"]
        characters = response.json()["characters"]
        assert len(characters) == 3

        # when we finalize the chargen with an invalid selected character id
        response = await client.post(
            build_url(CharacterURL.CHARGEN_FINALIZE),
            headers=token_company_admin,
            json={
                "session_id": chargen_session_id,
                "selected_character_id": str(PydanticObjectId()),
            },
        )
        # debug(response.json())

        # then we should get a 400 bad request response
        assert response.status_code == HTTP_400_BAD_REQUEST
