"""Test character generation."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY
from uuid import uuid4

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
)

from vapi.constants import CharacterClass, CharacterType
from vapi.db.sql_models.character import Character
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.chargen_session import ChargenSession
from vapi.db.sql_models.company import CompanySettings
from vapi.domain.handlers.character_autogeneration.constants import (
    AbilityFocus,
    AutoGenExperienceLevel,
)
from vapi.domain.services import GetModelByIdValidationService
from vapi.domain.services.user_svc import UserXPService
from vapi.domain.urls import Characters as CharacterURL
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.campaign import Campaign
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.user import User

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
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
        neutralize_after_response_hook: None,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify autogenerate character must be storyteller."""
        response = await client.post(
            build_url(
                CharacterURL.AUTOGENERATE,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
            json={"character_type": CharacterType.PLAYER.name},
        )
        assert response.status_code == HTTP_403_FORBIDDEN

    async def test_autogenerate_character(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user_storyteller: User,
        pg_mirror_campaign: Campaign,
        neutralize_after_response_hook: None,
        debug: Callable[[Any], None],
        mocker: Any,
    ) -> None:
        """Verify autogenerate character endpoint."""
        concept = await CharacterConcept.filter(is_archived=False).first()
        clan = await VampireClan.filter(is_archived=False, game_versions__contains=["V5"]).first()
        tribe = await WerewolfTribe.filter(is_archived=False).first()
        auspice = await WerewolfAuspice.filter(is_archived=False).first()
        spy1 = mocker.spy(GetModelByIdValidationService, "get_concept_by_uuid")
        spy2 = mocker.spy(GetModelByIdValidationService, "get_vampire_clan_by_uuid")
        spy3 = mocker.spy(GetModelByIdValidationService, "get_werewolf_tribe_by_uuid")
        spy4 = mocker.spy(GetModelByIdValidationService, "get_werewolf_auspice_by_uuid")

        # When creating a character with all random data
        response = await client.post(
            build_url(
                CharacterURL.AUTOGENERATE,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user_storyteller.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
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
        character = await Character.filter(id=character_id).first()
        assert character is not None
        assert str(character.company_id) == str(pg_mirror_company.id)
        assert str(character.user_creator_id) == str(pg_mirror_user_storyteller.id)
        assert str(character.user_player_id) == str(pg_mirror_user_storyteller.id)
        assert str(character.campaign_id) == str(pg_mirror_campaign.id)
        assert character.type == CharacterType.PLAYER
        assert character.character_class == CharacterClass.MORTAL
        assert str(character.concept_id) == str(concept.id)


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
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
        neutralize_after_response_hook: None,
        character_autogen_num_choices: int,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify start chargen endpoint."""
        # Given a company and user with the correct settings
        await CompanySettings.filter(company=pg_mirror_company).update(
            character_autogen_num_choices=character_autogen_num_choices
        )

        await UserXPService().add_xp(pg_mirror_user.id, pg_mirror_campaign.id, 100)

        # When we start chargen
        response = await client.post(
            build_url(
                CharacterURL.CHARGEN_START,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
        )
        # debug(response.json())

        # Then we should get a 201 created response and the characters should be temporary and have the correct chargen session id
        assert response.status_code == HTTP_201_CREATED
        assert response.json()["requires_selection"] == (character_autogen_num_choices > 1)

        characters = response.json()["characters"]
        assert len(characters) == character_autogen_num_choices
        for character in characters:
            assert character["is_temporary"] == (character_autogen_num_choices > 1)

    async def test_start_chargen_without_xp_cost(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
        neutralize_after_response_hook: None,
    ) -> None:
        """Verify start chargen endpoint with no XP."""
        # Given a company with character_autogen_num_choices set to 1 and xp cost of 100
        await CompanySettings.filter(company=pg_mirror_company).update(
            character_autogen_num_choices=1,
            character_autogen_xp_cost=100,
        )

        # When we start chargen
        response = await client.post(
            build_url(
                CharacterURL.CHARGEN_START,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
        )
        # debug(response.json())

        # Then we should get a 400 bad request response
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "User does not have enough XP to complete the action."

    async def test_finalize_chargen(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
        neutralize_after_response_hook: None,
    ) -> None:
        """Verify finalize chargen endpoint."""
        # Given a chargen session with 3 characters
        await CompanySettings.filter(company=pg_mirror_company).update(
            character_autogen_num_choices=3
        )
        await UserXPService().add_xp(pg_mirror_user.id, pg_mirror_campaign.id, 100)
        response = await client.post(
            build_url(
                CharacterURL.CHARGEN_START,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
        )
        chargen_session_id = response.json()["id"]
        characters = response.json()["characters"]
        assert len(characters) == 3
        selected_character_id = characters[0]["id"]

        # When we finalize the chargen
        response = await client.post(
            build_url(
                CharacterURL.CHARGEN_FINALIZE,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
            json={"session_id": chargen_session_id, "selected_character_id": selected_character_id},
        )
        # debug(response.json())

        # Then we should return the selected character and delete the other characters
        assert response.status_code == HTTP_201_CREATED
        assert response.json()["id"] == selected_character_id

        for character_id in [character["id"] for character in characters]:
            c = await Character.filter(id=character_id).first()
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
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
        neutralize_after_response_hook: None,
    ) -> None:
        """Verify finalize chargen endpoint with invalid session id."""
        # Given a chargen session with 3 characters
        await CompanySettings.filter(company=pg_mirror_company).update(
            character_autogen_num_choices=3
        )
        await UserXPService().add_xp(pg_mirror_user.id, pg_mirror_campaign.id, 100)
        response = await client.post(
            build_url(
                CharacterURL.CHARGEN_START,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
        )
        characters = response.json()["characters"]
        assert len(characters) == 3
        selected_character_id = characters[0]["id"]

        # When we finalize the chargen with an invalid session id
        response = await client.post(
            build_url(
                CharacterURL.CHARGEN_FINALIZE,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
            json={
                "session_id": "invalid-session-id",
                "selected_character_id": selected_character_id,
            },
        )
        # debug(response.json())

        # Then we should get a 400 bad request response
        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_finalize_chargen_invalid_selected_character_id(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
        neutralize_after_response_hook: None,
    ) -> None:
        """Verify finalize chargen endpoint with invalid selected character id."""
        # Given a chargen session with 3 characters
        await CompanySettings.filter(company=pg_mirror_company).update(
            character_autogen_num_choices=3
        )
        await UserXPService().add_xp(pg_mirror_user.id, pg_mirror_campaign.id, 100)
        response = await client.post(
            build_url(
                CharacterURL.CHARGEN_START,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
        )
        chargen_session_id = response.json()["id"]
        characters = response.json()["characters"]
        assert len(characters) == 3

        # When we finalize the chargen with an invalid selected character id
        response = await client.post(
            build_url(
                CharacterURL.CHARGEN_FINALIZE,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
            json={
                "session_id": chargen_session_id,
                "selected_character_id": str(uuid4()),
            },
        )
        # debug(response.json())

        # Then we should get a 400 bad request response
        assert response.status_code == HTTP_400_BAD_REQUEST


class TestChargenSessions:
    """Test chargen session list and detail endpoints."""

    async def test_list_chargen_sessions(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
        neutralize_after_response_hook: None,
    ) -> None:
        """Verify listing active chargen sessions returns sessions with characters."""
        # Given a chargen session exists
        await CompanySettings.filter(company=pg_mirror_company).update(
            character_autogen_num_choices=2
        )
        await UserXPService().add_xp(pg_mirror_user.id, pg_mirror_campaign.id, 100)
        start_response = await client.post(
            build_url(
                CharacterURL.CHARGEN_START,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
        )
        assert start_response.status_code == HTTP_201_CREATED
        session_id = start_response.json()["id"]

        # When listing active sessions
        response = await client.get(
            build_url(
                CharacterURL.CHARGEN_SESSIONS,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
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
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
        neutralize_after_response_hook: None,
    ) -> None:
        """Verify expired sessions are excluded from the list."""
        # Given an expired chargen session
        await CompanySettings.filter(company=pg_mirror_company).update(
            character_autogen_num_choices=1
        )
        await UserXPService().add_xp(pg_mirror_user.id, pg_mirror_campaign.id, 100)
        start_response = await client.post(
            build_url(
                CharacterURL.CHARGEN_START,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
        )
        assert start_response.status_code == HTTP_201_CREATED
        session_id = start_response.json()["id"]

        # Manually expire the session
        await ChargenSession.filter(id=session_id).update(
            expires_at=time_now() - timedelta(hours=1)
        )

        # When listing active sessions
        response = await client.get(
            build_url(
                CharacterURL.CHARGEN_SESSIONS,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
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
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
        pg_user_factory: Any,
        neutralize_after_response_hook: None,
    ) -> None:
        """Verify sessions from other users are not visible."""
        # Given a chargen session for base_user
        await CompanySettings.filter(company=pg_mirror_company).update(
            character_autogen_num_choices=1
        )
        await UserXPService().add_xp(pg_mirror_user.id, pg_mirror_campaign.id, 100)
        start_response = await client.post(
            build_url(
                CharacterURL.CHARGEN_START,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
        )
        assert start_response.status_code == HTTP_201_CREATED

        # Create a fake session for a different user
        other_user = await pg_user_factory(company=pg_mirror_company)
        fake_session = await ChargenSession.create(
            user=other_user,
            company=pg_mirror_company,
            campaign=pg_mirror_campaign,
            expires_at=time_now() + timedelta(hours=24),
            requires_selection=False,
        )

        # When listing sessions for base_user
        response = await client.get(
            build_url(
                CharacterURL.CHARGEN_SESSIONS,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
        )

        # Then only base_user's session appears, not the fake user's session
        assert response.status_code == HTTP_200_OK
        sessions = response.json()
        session_ids = [s["id"] for s in sessions]
        assert str(fake_session.id) not in session_ids
        for s in sessions:
            assert s["user_id"] == str(pg_mirror_user.id)

    async def test_get_chargen_session_by_id(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
        neutralize_after_response_hook: None,
    ) -> None:
        """Verify retrieving a session by ID returns the session with characters."""
        # Given a chargen session
        await CompanySettings.filter(company=pg_mirror_company).update(
            character_autogen_num_choices=2
        )
        await UserXPService().add_xp(pg_mirror_user.id, pg_mirror_campaign.id, 100)
        start_response = await client.post(
            build_url(
                CharacterURL.CHARGEN_START,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
        )
        assert start_response.status_code == HTTP_201_CREATED
        session_id = start_response.json()["id"]

        # When getting the session by ID
        response = await client.get(
            build_url(
                CharacterURL.CHARGEN_SESSION_DETAIL,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
                session_id=session_id,
            ),
            headers=token_global_admin,
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
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
    ) -> None:
        """Verify getting a non-existent session returns an error."""
        # When getting a session with a random ID
        response = await client.get(
            build_url(
                CharacterURL.CHARGEN_SESSION_DETAIL,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
                session_id=str(uuid4()),
            ),
            headers=token_global_admin,
        )

        # Then we get a 400 error
        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_get_chargen_session_expired(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
        neutralize_after_response_hook: None,
    ) -> None:
        """Verify getting an expired session returns an error."""
        # Given an expired session
        await CompanySettings.filter(company=pg_mirror_company).update(
            character_autogen_num_choices=1
        )
        await UserXPService().add_xp(pg_mirror_user.id, pg_mirror_campaign.id, 100)
        start_response = await client.post(
            build_url(
                CharacterURL.CHARGEN_START,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
        )
        assert start_response.status_code == HTTP_201_CREATED
        session_id = start_response.json()["id"]

        # Expire it
        await ChargenSession.filter(id=session_id).update(
            expires_at=time_now() - timedelta(hours=1)
        )

        # When getting the expired session
        response = await client.get(
            build_url(
                CharacterURL.CHARGEN_SESSION_DETAIL,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
                session_id=session_id,
            ),
            headers=token_global_admin,
        )

        # Then we get a 400 error
        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_start_chargen_creates_session_document(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
        neutralize_after_response_hook: None,
    ) -> None:
        """Verify starting chargen creates a ChargenSession in the database."""
        # Given
        await CompanySettings.filter(company=pg_mirror_company).update(
            character_autogen_num_choices=1
        )
        await UserXPService().add_xp(pg_mirror_user.id, pg_mirror_campaign.id, 100)

        # When starting chargen
        response = await client.post(
            build_url(
                CharacterURL.CHARGEN_START,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
        )

        # Then a ChargenSession document exists
        assert response.status_code == HTTP_201_CREATED
        session_id = response.json()["id"]
        session = await ChargenSession.filter(id=session_id).first()
        assert session is not None
        assert str(session.user_id) == str(pg_mirror_user.id)
        assert str(session.company_id) == str(pg_mirror_company.id)
        assert str(session.campaign_id) == str(pg_mirror_campaign.id)

    async def test_finalize_chargen_deletes_session_document(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
        neutralize_after_response_hook: None,
    ) -> None:
        """Verify finalizing chargen deletes the ChargenSession document."""
        # Given a chargen session with 3 characters
        await CompanySettings.filter(company=pg_mirror_company).update(
            character_autogen_num_choices=3
        )
        await UserXPService().add_xp(pg_mirror_user.id, pg_mirror_campaign.id, 100)
        start_response = await client.post(
            build_url(
                CharacterURL.CHARGEN_START,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
        )
        assert start_response.status_code == HTTP_201_CREATED
        session_id = start_response.json()["id"]
        characters = start_response.json()["characters"]
        selected_character_id = characters[0]["id"]

        # When finalizing
        response = await client.post(
            build_url(
                CharacterURL.CHARGEN_FINALIZE,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
            json={"session_id": session_id, "selected_character_id": selected_character_id},
        )
        assert response.status_code == HTTP_201_CREATED

        # Then the session document is deleted
        session = await ChargenSession.filter(id=session_id).first()
        assert session is None

    async def test_scheduled_task_cleans_expired_sessions(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        pg_mirror_company: Company,
        pg_mirror_global_admin: Any,
        pg_mirror_user: User,
        pg_mirror_campaign: Campaign,
        neutralize_after_response_hook: None,
    ) -> None:
        """Verify the scheduled task deletes expired sessions and their characters."""
        from vapi.lib.scheduled_tasks import purge_db_expired_items

        # Given an expired chargen session with characters
        await CompanySettings.filter(company=pg_mirror_company).update(
            character_autogen_num_choices=2
        )
        await UserXPService().add_xp(pg_mirror_user.id, pg_mirror_campaign.id, 100)
        start_response = await client.post(
            build_url(
                CharacterURL.CHARGEN_START,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
            ),
            headers=token_global_admin,
        )
        assert start_response.status_code == HTTP_201_CREATED
        session_id = start_response.json()["id"]
        character_ids = [c["id"] for c in start_response.json()["characters"]]

        # Expire the session
        await ChargenSession.filter(id=session_id).update(
            expires_at=time_now() - timedelta(hours=1)
        )

        # When the scheduled task runs
        await purge_db_expired_items({})

        # Then the session and its characters are deleted
        session = await ChargenSession.filter(id=session_id).first()
        assert session is None
        for character_id in character_ids:
            c = await Character.filter(id=character_id).first()
            assert c is None
