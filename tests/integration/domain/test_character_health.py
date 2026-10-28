"""Test character health controllers."""

from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient
from litestar.status_codes import HTTP_200_OK, HTTP_403_FORBIDDEN

from vapi.constants import AuditEntityType, UserRole
from vapi.db.sql_models.audit_log import AuditLog
from vapi.db.sql_models.character import Character
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain.urls import Characters

pytestmark = pytest.mark.anyio


class TestCharacterHealth:
    """Test character health controllers."""

    async def test_health_put_and_action(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_user: User,
        session_campaign: Any,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify setting health, applying an action, and the audit entity type."""
        # Given a V5 character
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            game_version="V5",
        )
        headers = token_global_admin | on_behalf_of_header
        url = build_url(Characters.HEALTH, company_id=session_company.id, character_id=character.id)
        await AuditLog.all().delete()

        # When setting health and then dealing damage
        put_response = await client.put(url, headers=headers, json={"damage": 1})
        action_response = await client.post(
            build_url(
                Characters.HEALTH_ACTIONS, company_id=session_company.id, character_id=character.id
            ),
            headers=headers,
            json={"action": "damage", "amount": 1},
        )
        get_response = await client.get(url, headers=headers)

        # Then both writes succeed, the GET reflects them, and both audit entries are health entries
        assert put_response.status_code == HTTP_200_OK
        assert put_response.json()["damage"] == 1
        assert action_response.status_code == HTTP_200_OK
        assert action_response.json()["damage"] == 2
        assert get_response.json() == action_response.json()
        for operation_id in ("setCharacterHealth", "applyCharacterHealthAction"):
            audit = await AuditLog.filter(operation_id=operation_id).first()
            assert audit.entity_type == AuditEntityType.CHARACTER_HEALTH

    async def test_health_write_requires_player_or_storyteller(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_campaign: Any,
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify a player who does not own the character cannot write its health."""
        # Given a character owned by one player and an unrelated player
        owner = await user_factory(role=UserRole.PLAYER.value, company=session_company)
        other = await user_factory(role=UserRole.PLAYER.value, company=session_company)
        character = await character_factory(
            company=session_company,
            user_player=owner,
            user_creator=owner,
            campaign=session_campaign,
        )

        # When the unrelated player sets the character's health
        response = await client.put(
            build_url(Characters.HEALTH, company_id=session_company.id, character_id=character.id),
            headers=token_global_admin | {"On-Behalf-Of": str(other.id)},
            json={"damage": 1},
        )

        # Then the response is forbidden
        assert response.status_code == HTTP_403_FORBIDDEN
