"""Idempotency middleware tests."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_409_CONFLICT

from vapi.constants import IDEMPOTENCY_KEY_HEADER, IGNORE_RATE_LIMIT_HEADER_KEY

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

pytestmark = pytest.mark.anyio


class TestIdempotencyMiddleware:
    """Test idempotency middleware behavior."""

    async def test_post_with_idempotency_key_returns_cached_response(
        self,
        client: AsyncClient,
        build_url: Callable[[str], str],
        token_company_admin: dict[str, str],
        base_user_storyteller,
    ) -> None:
        """Verify POST requests with same idempotency key and body return cached response."""
        from vapi.domain.urls import Campaigns

        # Given an idempotency key and a fixed request body
        idempotency_key = str(uuid.uuid4())
        headers = {
            **token_company_admin,
            IDEMPOTENCY_KEY_HEADER: idempotency_key,
            IGNORE_RATE_LIMIT_HEADER_KEY: "true",
        }
        request_body = {"name": "Test Campaign Idempotent", "description": "Test"}

        # When making a POST request
        response1 = await client.post(
            build_url(Campaigns.CREATE, user_id=base_user_storyteller.id),
            headers=headers,
            json=request_body,
        )

        # Then it should succeed
        assert response1.status_code == HTTP_201_CREATED

        # When making another POST with same idempotency key and same body
        response2 = await client.post(
            build_url(Campaigns.CREATE, user_id=base_user_storyteller.id),
            headers=headers,
            json=request_body,
        )

        # Then it should return the cached response
        assert response2.status_code == HTTP_201_CREATED
        assert response1.json()["id"] == response2.json()["id"]
        assert response1.json()["name"] == response2.json()["name"]

    async def test_post_with_same_key_different_body_raises_conflict(
        self,
        client: AsyncClient,
        build_url: Callable[[str], str],
        token_company_admin: dict[str, str],
        base_user_storyteller,
    ) -> None:
        """Verify POST requests with same idempotency key but different body raise ConflictError."""
        from vapi.domain.urls import Campaigns

        # Given an idempotency key
        idempotency_key = str(uuid.uuid4())
        headers = {
            **token_company_admin,
            IDEMPOTENCY_KEY_HEADER: idempotency_key,
            IGNORE_RATE_LIMIT_HEADER_KEY: "true",
        }

        # When making a POST request with a body
        response1 = await client.post(
            build_url(Campaigns.CREATE, user_id=base_user_storyteller.id),
            headers=headers,
            json={"name": "Campaign One", "description": "First"},
        )

        # Then it should succeed
        assert response1.status_code == HTTP_201_CREATED

        # When making another POST with same idempotency key but DIFFERENT body
        response2 = await client.post(
            build_url(Campaigns.CREATE, user_id=base_user_storyteller.id),
            headers=headers,
            json={"name": "Campaign Two", "description": "Second"},
        )

        # Then it should return a 409 Conflict error
        assert response2.status_code == HTTP_409_CONFLICT
        assert "different request body" in response2.json()["detail"]

    async def test_post_without_idempotency_key_creates_new_resources(
        self,
        client: AsyncClient,
        build_url: Callable[[str], str],
        token_company_admin: dict[str, str],
        base_user_storyteller,
    ) -> None:
        """Verify POST requests without idempotency header create new resources each time."""
        from vapi.domain.urls import Campaigns

        # Given headers without an idempotency key
        headers = {
            **token_company_admin,
            IGNORE_RATE_LIMIT_HEADER_KEY: "true",
        }

        # When making a POST request
        response1 = await client.post(
            build_url(Campaigns.CREATE, user_id=base_user_storyteller.id),
            headers=headers,
            json={"name": f"Test Campaign {uuid.uuid4()}", "description": "Test"},
        )

        # Then it should succeed
        assert response1.status_code == HTTP_201_CREATED

        # When making another POST without the idempotency header
        response2 = await client.post(
            build_url(Campaigns.CREATE, user_id=base_user_storyteller.id),
            headers=headers,
            json={"name": f"Test Campaign {uuid.uuid4()}", "description": "Test 2"},
        )

        # Then it should create a new resource (no caching without the header)
        assert response2.status_code == HTTP_201_CREATED
        assert response1.json()["id"] != response2.json()["id"]

    async def test_get_request_ignores_idempotency_header(
        self,
        client: AsyncClient,
        build_url: Callable[[str], str],
        token_company_user: dict[str, str],
    ) -> None:
        """Verify GET requests ignore the idempotency header entirely."""
        from vapi.domain.urls import Campaigns

        # Given an idempotency key on a GET request
        idempotency_key = str(uuid.uuid4())
        headers = {
            **token_company_user,
            IDEMPOTENCY_KEY_HEADER: idempotency_key,
            IGNORE_RATE_LIMIT_HEADER_KEY: "true",
        }

        # When making a GET request
        response = await client.get(build_url(Campaigns.LIST), headers=headers)

        # Then it should succeed (middleware skips GET requests)
        assert response.status_code == HTTP_200_OK
