"""Test how endpoints answer a malformed On-Behalf-Of header or company id."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from vapi.domain.urls import Campaigns, DiceRolls

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.user import User

pytestmark = pytest.mark.anyio


class TestMalformedActingUserHeader:
    """Verify a malformed On-Behalf-Of gets the same 400 on every kind of route."""

    @pytest.mark.parametrize(
        ("method", "url"),
        [
            ("POST", Campaigns.CREATE),
            ("GET", DiceRolls.LIST),
        ],
        ids=["manage-campaign-guard", "acting-user-provider"],
    )
    async def test_malformed_header_is_bad_request(
        self,
        method: str,
        url: str,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify a malformed On-Behalf-Of returns 400 whether a guard or the provider reads it."""
        # When requesting with a malformed On-Behalf-Of header
        response = await client.request(
            method,
            build_url(url, company_id=session_company.id),
            headers=token_global_admin | {"On-Behalf-Of": "not-a-uuid"},
            json={"name": "Malformed Header Campaign"} if method == "POST" else None,
        )

        # Then the request is rejected as a bad request
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "On-Behalf-Of header must be a valid UUID"


class TestMalformedCompanyId:
    """Verify a malformed company id is not-found for a global admin instead of a server error."""

    async def test_global_admin_malformed_company_id_is_not_found(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_user: User,
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify a global admin with a malformed company id gets 404."""
        # When a global admin requests a malformed company id with a valid acting user
        response = await client.get(
            build_url(DiceRolls.LIST, company_id="not-a-uuid"),
            headers=token_global_admin | {"On-Behalf-Of": str(session_user.id)},
        )

        # Then the company is not found
        assert response.status_code == HTTP_404_NOT_FOUND
