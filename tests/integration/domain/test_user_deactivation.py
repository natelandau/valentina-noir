"""End-to-end deactivation and last-admin protection tests for the user API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_403_FORBIDDEN,
    HTTP_409_CONFLICT,
)

from vapi.constants import UserRole
from vapi.db.sql_models.character import Character
from vapi.db.sql_models.user import User
from vapi.domain.urls import Users as UsersURL

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.campaign import Campaign
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.developer import Developer

pytestmark = pytest.mark.anyio


class TestDeactivation:
    """End-to-end tests for user deactivation and last-admin protection."""

    async def test_admin_deactivates_user_via_patch(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_user_admin: User,
        user_factory: Callable[..., User],
    ) -> None:
        """Verify an admin can deactivate a player via PATCH."""
        # Given a PLAYER in the same company as an existing admin
        player = await user_factory(company=session_company, role="PLAYER")

        # When the admin patches the player's role to DEACTIVATED
        response = await client.patch(
            build_url(UsersURL.UPDATE, user_id=player.id, company_id=session_company.id),
            headers=token_global_admin,
            json={
                "role": UserRole.DEACTIVATED.value,
                "requesting_user_id": str(session_user_admin.id),
            },
        )

        # Then the update succeeds and the role is DEACTIVATED
        assert response.status_code == HTTP_200_OK
        assert response.json()["role"] == UserRole.DEACTIVATED.value
        refreshed = await User.get(id=player.id)
        assert refreshed.role == UserRole.DEACTIVATED

    async def test_storyteller_cannot_deactivate_player(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_user_storyteller: User,
        user_factory: Callable[..., User],
    ) -> None:
        """Verify a storyteller cannot deactivate a player."""
        # Given a PLAYER and a STORYTELLER requester
        player = await user_factory(company=session_company, role="PLAYER")

        # When the storyteller attempts to deactivate the player
        response = await client.patch(
            build_url(UsersURL.UPDATE, user_id=player.id, company_id=session_company.id),
            headers=token_global_admin,
            json={
                "role": UserRole.DEACTIVATED.value,
                "requesting_user_id": str(session_user_storyteller.id),
            },
        )

        # Then the request is rejected with 403
        assert response.status_code == HTTP_403_FORBIDDEN

    async def test_deactivated_user_blocked_by_guard(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_campaign: Campaign,
        user_factory: Callable[..., User],
    ) -> None:
        """Verify the guard blocks any endpoint that targets a deactivated user via user_id."""
        # Given a DEACTIVATED user
        deactivated = await user_factory(company=session_company, role="DEACTIVATED")

        # When we hit an endpoint with the deactivated user as the user_id path param
        response = await client.get(
            build_url(
                UsersURL.EXPERIENCE_CAMPAIGN,
                user_id=deactivated.id,
                company_id=session_company.id,
                campaign_id=session_campaign.id,
            ),
            headers=token_global_admin,
        )

        # Then the guard rejects with 403 and a "deactivated" message
        assert response.status_code == HTTP_403_FORBIDDEN
        assert "deactivated" in response.json()["detail"].lower()

    async def test_deactivated_requester_blocked_via_service_layer(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_campaign: Campaign,
        user_factory: Callable[..., User],
    ) -> None:
        """Verify the service layer rejects a deactivated user as requesting_user_id."""
        # Given an active PLAYER target and a DEACTIVATED requester
        target = await user_factory(company=session_company, role="PLAYER")
        deactivated = await user_factory(company=session_company, role="DEACTIVATED")

        # When the deactivated user attempts to grant XP to the target
        response = await client.post(
            build_url(UsersURL.XP_ADD, user_id=target.id, company_id=session_company.id),
            headers=token_global_admin,
            json={
                "amount": 10,
                "requesting_user_id": str(deactivated.id),
                "campaign_id": str(session_campaign.id),
            },
        )

        # Then the service layer rejects with 403 (_assert_requester_active)
        assert response.status_code == HTTP_403_FORBIDDEN

    async def test_deactivating_user_preserves_characters(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_campaign: Campaign,
        session_user_admin: User,
        user_factory: Callable[..., User],
        character_factory: Callable[..., Any],
    ) -> None:
        """Verify PATCHing a user to DEACTIVATED leaves their characters intact in the database."""
        # Given an active PLAYER with a played character
        player = await user_factory(company=session_company, role="PLAYER")
        character = await character_factory(
            company=session_company,
            user_player=player,
            user_creator=player,
            campaign=session_campaign,
        )

        # When the admin deactivates the player
        response = await client.patch(
            build_url(UsersURL.UPDATE, user_id=player.id, company_id=session_company.id),
            headers=token_global_admin,
            json={
                "role": UserRole.DEACTIVATED.value,
                "requesting_user_id": str(session_user_admin.id),
            },
        )

        # Then the deactivation succeeds and the character still exists, unarchived,
        # with its user_player link intact (asset integrity preserved on deactivation)
        assert response.status_code == HTTP_200_OK
        refreshed = await Character.get(id=character.id).prefetch_related("user_player")
        assert refreshed.is_archived is False
        assert refreshed.user_player is not None
        assert str(refreshed.user_player.id) == str(player.id)

    async def test_last_admin_deactivation_blocked(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        session_global_admin: Developer,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify deactivating the last active admin is blocked with 409."""
        # Given a company with exactly one ADMIN
        company = await company_factory(name="solo-admin-co", email="solo-admin@test.com")
        solo_admin = await user_factory(company=company, role="ADMIN")

        # When the solo admin tries to deactivate themselves
        response = await client.patch(
            build_url(UsersURL.UPDATE, user_id=solo_admin.id, company_id=company.id),
            headers=token_global_admin,
            json={
                "role": UserRole.DEACTIVATED.value,
                "requesting_user_id": str(solo_admin.id),
            },
        )

        # Then the request is rejected with 409
        assert response.status_code == HTTP_409_CONFLICT

    async def test_last_admin_delete_blocked(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        session_global_admin: Developer,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify deleting the last active admin is blocked with 409."""
        # Given a company with exactly one ADMIN
        company = await company_factory(name="solo-admin-del-co", email="solo-admin-del@test.com")
        solo_admin = await user_factory(company=company, role="ADMIN")

        # When the solo admin tries to delete themselves
        response = await client.delete(
            build_url(UsersURL.DELETE, user_id=solo_admin.id, company_id=company.id),
            headers=token_global_admin,
            params={"requesting_user_id": str(solo_admin.id)},
        )

        # Then the request is rejected with 409
        assert response.status_code == HTTP_409_CONFLICT
        # And the admin is not archived
        refreshed = await User.get(id=solo_admin.id)
        assert refreshed.is_archived is False

    async def test_player_self_patch_role_escalation_blocked(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        user_factory: Callable[..., User],
    ) -> None:
        """Verify a player cannot self-escalate their role to ADMIN via PATCH."""
        # Given a PLAYER
        player = await user_factory(company=session_company, role="PLAYER")

        # When the player attempts to patch their own role to ADMIN
        response = await client.patch(
            build_url(UsersURL.UPDATE, user_id=player.id, company_id=session_company.id),
            headers=token_global_admin,
            json={
                "role": UserRole.ADMIN.value,
                "requesting_user_id": str(player.id),
            },
        )

        # Then the request is rejected with 403
        assert response.status_code == HTTP_403_FORBIDDEN
        refreshed = await User.get(id=player.id)
        assert refreshed.role == UserRole.PLAYER
