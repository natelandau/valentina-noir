"""Test the after response hooks.

These are smoke tests to ensure the hooks are working as expected. We do not test that they are added to every endpoint that should have them. This is because the hooks are applied to every endpoint that uses the `after_response` parameter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED

from vapi.config import settings
from vapi.constants import AUTH_HEADER_KEY, UserRole
from vapi.db.models import AuditLog
from vapi.domain.urls import Users as UsersURL
from vapi.lib.crypt import hmac_sha256_hex

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient
    from redis.asyncio import Redis

    from vapi.db.models import Company, Developer, User

pytestmark = pytest.mark.anyio


class TestAfterResponseHooks:
    """Test the after response hooks."""

    async def test_audit_log_and_delete_api_key_cache(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_user: User,
        base_company: Company,
        token_company_owner: dict[str, str],
        base_developer_company_owner: Developer,
        redis: Redis,
        user_factory: Callable[[dict[str, ...]], User],
        debug: Callable[[...], None],
    ) -> None:
        """Verify audit log and delete api key cache hook."""
        await AuditLog.delete_all()

        ### BUILD A RESPONSE CACHE ENTRY ###
        # Given a user and an API key
        api_key = token_company_owner[AUTH_HEADER_KEY]
        fingerprint = hmac_sha256_hex(data=api_key)

        # When: making a cacheable GET request
        response = await client.get(build_url(UsersURL.LIST), headers=token_company_owner)
        assert response.status_code == HTTP_200_OK
        assert len(response.json()["items"]) == 1
        assert response.json()["items"][0]["id"] == str(base_user.id)

        # Then: the response should be in the Redis cache
        cache_prefix = f"{settings.slug}:{settings.stores.response_cache_key}:{fingerprint}"

        cached_keys = [key async for key in redis.scan_iter(match=f"{cache_prefix}:*")]

        assert len(cached_keys) > 0, f"Expected cache entries with prefix {cache_prefix}"

        ## CREATE A NEW USER AND CREATE AN AUDIT LOG AND CLEAR THE CACHE ##
        # When we create a user

        requesting_user = await user_factory(company_id=base_company.id, role=UserRole.ADMIN)
        response = await client.post(
            build_url(UsersURL.CREATE),
            headers=token_company_owner,
            json={
                "name": "Test User",
                "email": "test@test.com",
                "role": "ADMIN",
                "discord_profile": {"username": "discord_username"},
                "requesting_user_id": str(requesting_user.id),
            },
        )
        assert response.status_code == HTTP_201_CREATED
        assert response.json()["discord_profile"]["username"] == "discord_username"

        # Then: the response cache should be deleted
        cached_keys = [key async for key in redis.scan_iter(match=f"{cache_prefix}:*")]
        assert len(cached_keys) == 0, f"Expected no cache entries with prefix {cache_prefix}"

        # And an audit log should be created
        audit = await AuditLog.find_one()
        assert audit.developer_id == base_developer_company_owner.id
        assert audit.summary == "Create user"
        assert (
            audit.handler
            == "vapi.domain.controllers.user.user_controller.UserController.create_user"
        )
        assert audit.handler_name == "create_user"
        assert audit.operation_id == "createUser"
        assert audit.method == "POST"
        assert audit.url == f"http://testserver/api/v1/companies/{base_company.id}/users"
        assert audit.request_json == {
            "name": "Test User",
            "email": "test@test.com",
            "role": "ADMIN",
            "discord_profile": {"username": "discord_username"},
            "requesting_user_id": str(requesting_user.id),
        }
        assert (
            audit.request_body
            == f'{{"name":"Test User","email":"test@test.com","role":"ADMIN","discord_profile":{{"username":"discord_username"}},"requesting_user_id":"{requesting_user.id!s}"}}'
        )
        assert audit.path_params == {"company_id": str(base_company.id)}

        # cleanup
        await requesting_user.delete()
