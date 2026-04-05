"""Test error pipeline - verify errors are correctly converted to HTTP responses.

This module contains integration tests that verify each error type is properly
propagated through the middleware and converted to the correct HTTP response
format following RFC 7807 Problem Details.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from litestar.status_codes import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from vapi.db.sql_models.character_sheet import Trait, TraitCategory
from vapi.domain.urls import Characters as CharacterURL

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.campaign import Campaign
    from vapi.db.sql_models.character import Character, CharacterTrait
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.developer import Developer
    from vapi.db.sql_models.user import User

pytestmark = pytest.mark.anyio


class TestErrorPipeline:
    """Verify error types are correctly converted to HTTP responses."""

    async def test_validation_error_returns_400_with_invalid_parameters(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        token_global_admin: dict[str, str],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify ValidationError from service layer returns proper HTTP 400 response with invalid_parameters."""
        # Given a request that triggers a ValidationError (vampire without clan)
        response = await client.post(
            build_url(
                CharacterURL.CREATE,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=session_campaign.id,
            ),
            headers=token_global_admin,
            json={
                "name_first": "ErrorPipelineTest",
                "name_last": "Vampire",
                "character_class": "VAMPIRE",
                "game_version": "V5",
                "type": "PLAYER",
            },
        )

        # Then the response should be HTTP 400 with RFC 7807 structure
        assert response.status_code == HTTP_400_BAD_REQUEST
        response_data = response.json()

        # Verify RFC 7807 Problem Details structure
        assert "status" in response_data
        assert response_data["status"] == HTTP_400_BAD_REQUEST
        assert "title" in response_data
        assert "detail" in response_data
        assert "instance" in response_data

        # Verify invalid_parameters format for ValidationError
        assert "invalid_parameters" in response_data
        assert isinstance(response_data["invalid_parameters"], list)
        assert len(response_data["invalid_parameters"]) > 0
        assert "field" in response_data["invalid_parameters"][0]
        assert "message" in response_data["invalid_parameters"][0]

    async def test_not_found_error_returns_404(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        token_global_admin: dict[str, str],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify NotFoundError returns proper HTTP 404 response."""
        # Given a request for a non-existent character
        non_existent_id = uuid4()
        response = await client.get(
            build_url(
                CharacterURL.DETAIL,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=session_campaign.id,
                character_id=non_existent_id,
            ),
            headers=token_global_admin,
        )

        # Then the response should be HTTP 404 with RFC 7807 structure
        assert response.status_code == HTTP_404_NOT_FOUND
        response_data = response.json()

        # Verify RFC 7807 Problem Details structure
        assert "status" in response_data
        assert response_data["status"] == HTTP_404_NOT_FOUND
        assert "title" in response_data
        assert "detail" in response_data
        assert "instance" in response_data

    async def test_conflict_error_returns_409(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        token_global_admin: dict[str, str],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify ConflictError returns proper HTTP 409 response."""
        # Given a character with a trait already assigned
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            campaign=session_campaign,
        )
        trait = await Trait.filter(is_archived=False).first()
        await character_trait_factory(character=character, trait=trait)
        trait_category = await TraitCategory.filter(is_archived=False).first()

        # When we try to create a custom trait with the same name
        response = await client.post(
            build_url(
                CharacterURL.TRAIT_CREATE,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=session_campaign.id,
                character_id=character.id,
            ),
            headers=token_global_admin,
            json={
                "name": trait.name,
                "description": "Test Description",
                "max_value": 5,
                "min_value": 0,
                "show_when_zero": True,
                "parent_category_id": str(trait_category.id),
                "value": 1,
            },
        )

        # Then the response should be HTTP 409
        assert response.status_code == HTTP_409_CONFLICT
        response_data = response.json()

        # Verify RFC 7807 Problem Details structure
        assert "status" in response_data
        assert response_data["status"] == HTTP_409_CONFLICT
        assert "title" in response_data
        assert "instance" in response_data

    async def test_litestar_validation_error_returns_400(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        token_global_admin: dict[str, str],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify Tortoise ValidationError is converted to proper HTTP 400 response."""
        # Given a request with a name_first that violates MinLengthValidator(3)
        response = await client.post(
            build_url(
                CharacterURL.CREATE,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=session_campaign.id,
            ),
            headers=token_global_admin,
            json={
                "name_first": "a",  # Too short — rejected by MinLengthValidator(3)
                "name_last": "Test",
                "character_class": "MORTAL",
                "game_version": "V5",
                "type": "PLAYER",
            },
        )

        # Then the response should be HTTP 400
        assert response.status_code == HTTP_400_BAD_REQUEST
        response_data = response.json()

        # Verify RFC 7807 Problem Details structure
        assert "status" in response_data
        assert response_data["status"] == HTTP_400_BAD_REQUEST
        assert "title" in response_data
        assert "instance" in response_data

        # Verify invalid_parameters is present for validation errors
        assert "invalid_parameters" in response_data
