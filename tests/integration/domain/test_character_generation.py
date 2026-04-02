"""Test character generation."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY

import pytest
from beanie import PydanticObjectId
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
)

from vapi.constants import CharacterClass, CharacterType
from vapi.db.models import (
    Character,
    CharacterConcept,
    ChargenSession,
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
from vapi.utils.time import time_now

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

    @pytest.mark.xfail(
        reason="CharacterService now uses Tortoise but chargen still creates Beanie characters. "
        "Resolves in Session 9.5 when chargen migrates.",
        strict=True,
    )
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


@pytest.mark.xfail(
    reason="CharacterService now uses Tortoise but chargen still creates Beanie characters. "
    "Resolves in Session 9.5 when chargen migrates.",
    strict=False,
)
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

        characters = response.json()["characters"]
        assert len(characters) == character_autogen_num_choices
        for character in characters:
            assert character["is_temporary"] == (character_autogen_num_choices > 1)
            assert character["is_chargen"] is True

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
        chargen_session_id = response.json()["id"]
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
                assert c.is_chargen is False
                assert c.is_archived is False

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
        chargen_session_id = response.json()["id"]
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


@pytest.mark.xfail(
    reason="CharacterService now uses Tortoise but chargen still creates Beanie characters. "
    "Resolves in Session 9.5 when chargen migrates.",
    strict=False,
)
class TestChargenSessions:
    """Test chargen session list and detail endpoints."""

    async def test_list_chargen_sessions(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
    ) -> None:
        """Verify listing active chargen sessions returns sessions with characters."""
        # Given a chargen session exists
        base_company.settings.character_autogen_num_choices = 2
        await base_company.save()
        await base_user.add_xp(base_campaign.id, 100)
        start_response = await client.post(
            build_url(CharacterURL.CHARGEN_START),
            headers=token_company_admin,
        )
        assert start_response.status_code == HTTP_201_CREATED
        session_id = start_response.json()["id"]

        # When listing active sessions
        response = await client.get(
            build_url(CharacterURL.CHARGEN_SESSIONS),
            headers=token_company_admin,
        )

        # Then the session appears with characters populated
        assert response.status_code == HTTP_200_OK
        sessions = response.json()
        assert len(sessions) >= 1
        matching = [s for s in sessions if s["id"] == session_id]
        assert len(matching) == 1
        assert len(matching[0]["characters"]) == 2
        assert matching[0]["requires_selection"] is True

    async def test_list_chargen_sessions_excludes_expired(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
    ) -> None:
        """Verify expired sessions are excluded from the list."""
        # Given an expired chargen session
        base_company.settings.character_autogen_num_choices = 1
        await base_company.save()
        await base_user.add_xp(base_campaign.id, 100)
        start_response = await client.post(
            build_url(CharacterURL.CHARGEN_START),
            headers=token_company_admin,
        )
        assert start_response.status_code == HTTP_201_CREATED
        session_id = start_response.json()["id"]

        # Manually expire the session
        session = await ChargenSession.get(session_id)
        session.expires_at = time_now() - timedelta(hours=1)
        await session.save()

        # When listing active sessions
        response = await client.get(
            build_url(CharacterURL.CHARGEN_SESSIONS),
            headers=token_company_admin,
        )

        # Then the expired session is not included
        assert response.status_code == HTTP_200_OK
        sessions = response.json()
        matching = [s for s in sessions if s["id"] == session_id]
        assert len(matching) == 0

    async def test_list_chargen_sessions_excludes_other_users(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
    ) -> None:
        """Verify sessions from other users are not visible."""
        # Given a chargen session for base_user
        base_company.settings.character_autogen_num_choices = 1
        await base_company.save()
        await base_user.add_xp(base_campaign.id, 100)
        start_response = await client.post(
            build_url(CharacterURL.CHARGEN_START),
            headers=token_company_admin,
        )
        assert start_response.status_code == HTTP_201_CREATED

        # Create a fake session for a different user
        fake_session = ChargenSession(
            user_id=PydanticObjectId(),
            company_id=base_company.id,
            campaign_id=base_campaign.id,
            characters=[],
            expires_at=time_now() + timedelta(hours=24),
            requires_selection=False,
        )
        await fake_session.save()

        # When listing sessions for base_user
        response = await client.get(
            build_url(CharacterURL.CHARGEN_SESSIONS),
            headers=token_company_admin,
        )

        # Then only base_user's session appears, not the fake user's session
        assert response.status_code == HTTP_200_OK
        sessions = response.json()
        session_ids = [s["id"] for s in sessions]
        assert str(fake_session.id) not in session_ids
        for s in sessions:
            assert s["user_id"] == str(base_user.id)

    async def test_get_chargen_session_by_id(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
    ) -> None:
        """Verify retrieving a session by ID returns the session with characters."""
        # Given a chargen session
        base_company.settings.character_autogen_num_choices = 2
        await base_company.save()
        await base_user.add_xp(base_campaign.id, 100)
        start_response = await client.post(
            build_url(CharacterURL.CHARGEN_START),
            headers=token_company_admin,
        )
        assert start_response.status_code == HTTP_201_CREATED
        session_id = start_response.json()["id"]

        # When getting the session by ID
        response = await client.get(
            build_url(CharacterURL.CHARGEN_SESSION_DETAIL, session_id=session_id),
            headers=token_company_admin,
        )

        # Then the session is returned with characters
        assert response.status_code == HTTP_200_OK
        assert response.json()["id"] == session_id
        assert len(response.json()["characters"]) == 2
        assert response.json()["requires_selection"] is True

    async def test_get_chargen_session_not_found(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
    ) -> None:
        """Verify getting a non-existent session returns an error."""
        # When getting a session with a random ID
        response = await client.get(
            build_url(CharacterURL.CHARGEN_SESSION_DETAIL, session_id=str(PydanticObjectId())),
            headers=token_company_admin,
        )

        # Then we get a 400 error
        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_get_chargen_session_expired(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
    ) -> None:
        """Verify getting an expired session returns an error."""
        # Given an expired session
        base_company.settings.character_autogen_num_choices = 1
        await base_company.save()
        await base_user.add_xp(base_campaign.id, 100)
        start_response = await client.post(
            build_url(CharacterURL.CHARGEN_START),
            headers=token_company_admin,
        )
        assert start_response.status_code == HTTP_201_CREATED
        session_id = start_response.json()["id"]

        # Expire it
        session = await ChargenSession.get(session_id)
        session.expires_at = time_now() - timedelta(hours=1)
        await session.save()

        # When getting the expired session
        response = await client.get(
            build_url(CharacterURL.CHARGEN_SESSION_DETAIL, session_id=session_id),
            headers=token_company_admin,
        )

        # Then we get a 400 error
        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_start_chargen_creates_session_document(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
    ) -> None:
        """Verify starting chargen creates a ChargenSession in the database."""
        # Given
        base_company.settings.character_autogen_num_choices = 1
        await base_company.save()
        await base_user.add_xp(base_campaign.id, 100)

        # When starting chargen
        response = await client.post(
            build_url(CharacterURL.CHARGEN_START),
            headers=token_company_admin,
        )

        # Then a ChargenSession document exists
        assert response.status_code == HTTP_201_CREATED
        session_id = response.json()["id"]
        session = await ChargenSession.get(session_id)
        assert session is not None
        assert session.user_id == base_user.id
        assert session.company_id == base_company.id
        assert session.campaign_id == base_campaign.id

    async def test_finalize_chargen_deletes_session_document(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
    ) -> None:
        """Verify finalizing chargen deletes the ChargenSession document."""
        # Given a chargen session with 3 characters
        base_company.settings.character_autogen_num_choices = 3
        await base_company.save()
        await base_user.add_xp(base_campaign.id, 100)
        start_response = await client.post(
            build_url(CharacterURL.CHARGEN_START),
            headers=token_company_admin,
        )
        assert start_response.status_code == HTTP_201_CREATED
        session_id = start_response.json()["id"]
        characters = start_response.json()["characters"]
        selected_character_id = characters[0]["id"]

        # When finalizing
        response = await client.post(
            build_url(CharacterURL.CHARGEN_FINALIZE),
            headers=token_company_admin,
            json={"session_id": session_id, "selected_character_id": selected_character_id},
        )
        assert response.status_code == HTTP_201_CREATED

        # Then the session document is deleted
        session = await ChargenSession.get(session_id)
        assert session is None

    async def test_scheduled_task_cleans_expired_sessions(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
    ) -> None:
        """Verify the scheduled task deletes expired sessions and their characters."""
        from vapi.lib.scheduled_tasks import purge_db_expired_items

        # Given an expired chargen session with characters
        base_company.settings.character_autogen_num_choices = 2
        await base_company.save()
        await base_user.add_xp(base_campaign.id, 100)
        start_response = await client.post(
            build_url(CharacterURL.CHARGEN_START),
            headers=token_company_admin,
        )
        assert start_response.status_code == HTTP_201_CREATED
        session_id = start_response.json()["id"]
        character_ids = [c["id"] for c in start_response.json()["characters"]]

        # Expire the session
        session = await ChargenSession.get(session_id)
        session.expires_at = time_now() - timedelta(hours=1)
        await session.save()

        # When the scheduled task runs
        await purge_db_expired_items({})

        # Then the session and its characters are deleted
        session = await ChargenSession.get(session_id)
        assert session is None
        for character_id in character_ids:
            c = await Character.get(character_id)
            assert c is None
