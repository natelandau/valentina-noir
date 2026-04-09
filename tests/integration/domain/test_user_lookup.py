"""Integration tests for the cross-company user lookup endpoint."""

import pytest
from httpx import AsyncClient
from litestar.status_codes import HTTP_200_OK, HTTP_400_BAD_REQUEST

from vapi.db.sql_models.company import Company
from vapi.db.sql_models.developer import Developer
from vapi.domain.urls import UserLookup

pytestmark = pytest.mark.anyio


class TestUserLookupController:
    """Test GET /api/v1/users/lookup."""

    async def test_lookup_by_email_returns_results(
        self,
        client: AsyncClient,
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory,
    ) -> None:
        """Verify lookup by email returns matching users with expected response shape."""
        # Given a user on the session company
        user = await user_factory(company=session_company, email="lookup-test@example.com")

        # When looking up by email
        response = await client.get(
            UserLookup.LOOKUP,
            params={"email": "lookup-test@example.com"},
            headers=token_company_user,
        )

        # Then the response contains the match
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        match = next(r for r in data if r["user_id"] == str(user.id))
        assert match["company_id"] == str(session_company.id)
        assert match["company_name"] == session_company.name
        assert match["role"] == "PLAYER"

    async def test_lookup_no_params_returns_400(
        self,
        client: AsyncClient,
        token_company_user: dict[str, str],
    ) -> None:
        """Verify omitting all query parameters returns 400."""
        # When calling lookup with no parameters
        response = await client.get(
            UserLookup.LOOKUP,
            headers=token_company_user,
        )

        # Then a 400 error is returned
        assert response.status_code == HTTP_400_BAD_REQUEST
