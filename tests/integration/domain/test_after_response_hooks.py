"""Test the after response hooks.

These are smoke tests to ensure the hooks are working as expected. We do not test that they are added to every endpoint that should have them. This is because the hooks are applied to every endpoint that uses the `after_response` parameter.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED

from vapi.config import settings
from vapi.constants import AUTH_HEADER_KEY
from vapi.db.sql_models.audit_log import AuditLog
from vapi.db.sql_models.company import Company
from vapi.domain.urls import Users as UsersURL
from vapi.lib.crypt import hmac_sha256_hex
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient
    from redis.asyncio import Redis

    from vapi.db.sql_models.developer import Developer
    from vapi.db.sql_models.user import User

pytestmark = pytest.mark.anyio


class TestAfterResponseHooks:
    """Test the after response hooks."""

    @pytest.mark.clean_db
    async def test_post_data_update_hook(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_owner: dict[str, str],
        redis: Redis,
        mirror_company: Company,
        mirror_company_owner: Developer,
        mirror_user: User,
        user_factory: Callable[..., User],
        debug: Callable[[...], None],
    ) -> None:
        """Verify audit log and delete api key cache hook."""
        await AuditLog.all().delete()
        # Reset the Tortoise company timestamp so the hook update is detectable
        mirror_company.resources_modified_at = time_now() - timedelta(days=10)
        await mirror_company.save()

        ### BUILD A RESPONSE CACHE ENTRY ###
        # Given a user and an API key
        api_key = token_company_owner[AUTH_HEADER_KEY]
        fingerprint = hmac_sha256_hex(data=api_key)

        # When: making a cacheable GET request
        response = await client.get(
            build_url(UsersURL.LIST, company_id=mirror_company.id),
            headers=token_company_owner,
        )
        assert response.status_code == HTTP_200_OK
        assert len(response.json()["items"]) >= 1

        # Then: the response should be in the Redis cache
        cache_prefix = f"{settings.slug}:{settings.stores.response_cache_key}:{fingerprint}"

        cached_keys = [key async for key in redis.scan_iter(match=f"{cache_prefix}:*")]

        assert len(cached_keys) > 0, f"Expected cache entries with prefix {cache_prefix}"

        ## CREATE A NEW USER AND CREATE AN AUDIT LOG AND CLEAR THE CACHE ##
        # When we create a user

        requesting_user = await user_factory(company=mirror_company, role="ADMIN")
        response = await client.post(
            build_url(UsersURL.CREATE, company_id=mirror_company.id),
            headers=token_company_owner,
            json={
                "name_first": "Test",
                "name_last": "User",
                "username": "test_user",
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

        # And an audit log should be created in Tortoise
        audit = await AuditLog.first()
        assert audit.developer_id == mirror_company_owner.id
        assert audit.summary == "Create user"
        assert (
            audit.handler
            == "vapi.domain.controllers.user.user_controller.UserController.create_user"
        )
        assert audit.handler_name == "create_user"
        assert audit.operation_id == "createUser"
        assert audit.method == "POST"
        assert audit.url == f"http://testserver/api/v1/companies/{mirror_company.id}/users"
        assert audit.request_json == {
            "name_first": "Test",
            "name_last": "User",
            "username": "test_user",
            "email": "test@test.com",
            "role": "ADMIN",
            "discord_profile": {"username": "discord_username"},
            "requesting_user_id": str(requesting_user.id),
        }
        assert audit.path_params == {"company_id": str(mirror_company.id)}

        # Then: the Tortoise company resources_modified_at should be updated
        updated_company = await Company.get(id=mirror_company.id)
        assert updated_company.resources_modified_at > time_now() - timedelta(days=1)
