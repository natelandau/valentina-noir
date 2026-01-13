"""Test developer."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED

from vapi.db.models import Developer
from vapi.domain.urls import Developers

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_developer_me(
    client: "AsyncClient",
    token_global_admin: dict[str, str],
    base_developer_global_admin: "Developer",
    build_url: Callable[[str, Any], str],
    debug: Callable[[Any], None],
) -> None:
    """Test the developer me endpoint."""
    response = await client.get(build_url(Developers.ME), headers=token_global_admin)

    assert response.status_code == HTTP_200_OK
    assert response.json() == base_developer_global_admin.model_dump(
        exclude={
            "is_archived",
            "archive_date",
            "api_key_fingerprint",
            "hashed_api_key",
            "is_global_admin",
        },
        mode="json",
    )


async def test_developer_new_key(
    client: "AsyncClient",
    token_global_admin: dict[str, str],
    base_developer_global_admin: Developer,
    build_url: Callable[[str, Any], str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the developer can generate a new API key."""
    db_developer = await Developer.get(base_developer_global_admin.id)
    original_hashed_api_key = db_developer.hashed_api_key
    original_api_key_fingerprint = db_developer.api_key_fingerprint

    response = await client.post(
        build_url(Developers.NEW_KEY),
        headers=token_global_admin,
    )
    # debug(response.json())
    json_data = response.json()
    assert response.status_code == HTTP_201_CREATED

    assert json_data["api_key"] is not None
    assert json_data["username"] == base_developer_global_admin.username
    assert json_data["email"] == base_developer_global_admin.email

    db_developer = await Developer.get(base_developer_global_admin.id)
    assert db_developer.key_generated is not None
    assert db_developer.key_generated.strftime("%Y-%m-%dT%H:%M:%SZ") == json_data["key_generated"]
    assert db_developer.hashed_api_key is not None
    assert db_developer.api_key_fingerprint is not None
    assert db_developer.hashed_api_key != original_hashed_api_key
    assert db_developer.api_key_fingerprint != original_api_key_fingerprint

    # Cleanup
    await db_developer.delete()


async def test_developer_update(
    client: "AsyncClient",
    token_global_admin: dict[str, str],
    base_developer_global_admin: Developer,
    build_url: Callable[[str, Any], str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the developer can update their information."""
    response = await client.patch(
        build_url(Developers.UPDATE),
        headers=token_global_admin,
        json={"username": "updated user", "email": "updated@test.com"},
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["username"] == "updated-user"
    assert response.json()["email"] == "updated@test.com"

    db_developer = await Developer.get(base_developer_global_admin.id)
    assert db_developer.username == "updated-user"
    assert db_developer.email == "updated@test.com"
