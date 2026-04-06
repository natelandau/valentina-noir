"""Test Global Admin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
)

from vapi.db.sql_models.developer import Developer
from vapi.domain.urls import GlobalAdmin

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_admin_list_developers(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_global_admin: Developer,
    developer_factory: Callable[..., Developer],
) -> None:
    """Verify the admin can list Developers."""
    # Given a new developer exists alongside the global admin
    new_developer = await developer_factory()

    # When listing developers
    response = await client.get(build_url(GlobalAdmin.DEVELOPERS), headers=token_global_admin)

    # Then the response is successful and contains at least the admin and the new developer
    assert response.status_code == HTTP_200_OK
    json_data = response.json()
    returned_ids = [item["id"] for item in json_data["items"]]
    assert str(new_developer.id) in returned_ids
    assert str(session_global_admin.id) in returned_ids


async def test_get_developer(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_global_admin: Developer,
) -> None:
    """Verify the admin can get a Developer."""
    # When retrieving the global admin developer
    response = await client.get(
        build_url(GlobalAdmin.DEVELOPER_DETAIL, developer_id=session_global_admin.id),
        headers=token_global_admin,
    )

    # Then the response contains the developer data
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["id"] == str(session_global_admin.id)
    assert data["username"] == session_global_admin.username
    assert data["email"] == session_global_admin.email
    assert data["is_global_admin"] == session_global_admin.is_global_admin
    assert "companies" in data
    assert isinstance(data["companies"], list)


async def test_post_developer(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_global_admin: Developer,
) -> None:
    """Verify the admin can create a Developer."""
    # When creating a new developer
    response = await client.post(
        build_url(GlobalAdmin.DEVELOPER_CREATE),
        headers=token_global_admin,
        json={"username": "test user", "email": "test@test.com", "is_global_admin": False},
    )

    # Then the response is successful
    assert response.status_code == HTTP_201_CREATED
    data = response.json()
    assert data["username"] == "test-user"
    assert data["email"] == "test@test.com"
    assert not data["is_global_admin"]
    assert data["companies"] == []

    # And the developer exists in the database
    db_developer = await Developer.get(id=data["id"])
    assert db_developer.username == "test-user"
    assert db_developer.email == "test@test.com"
    assert not db_developer.is_global_admin


async def test_patch_developer(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_global_admin: Developer,
    developer_factory: Callable[..., Developer],
) -> None:
    """Verify the admin can patch a Developer."""
    # Given a developer
    new_developer = await developer_factory(username="original")

    # When patching the developer
    response = await client.patch(
        build_url(GlobalAdmin.DEVELOPER_DETAIL, developer_id=new_developer.id),
        headers=token_global_admin,
        json={"username": "patched"},
    )

    # Then the response has updated data
    assert response.status_code == HTTP_200_OK
    assert response.json()["username"] == "patched"
    assert response.json()["email"] == new_developer.email
    assert response.json()["is_global_admin"] == new_developer.is_global_admin

    # And the database is updated
    db_developer = await Developer.get(id=new_developer.id)
    assert db_developer.username == "patched"
    assert db_developer.email == new_developer.email
    assert db_developer.is_global_admin == new_developer.is_global_admin


async def test_delete_developer(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_global_admin: Developer,
    developer_factory: Callable[..., Developer],
) -> None:
    """Verify the admin can delete a Developer."""
    # Given a developer
    new_developer = await developer_factory()

    # When deleting the developer
    response = await client.delete(
        build_url(GlobalAdmin.DEVELOPER_DETAIL, developer_id=new_developer.id),
        headers=token_global_admin,
    )

    # Then the response indicates success
    assert response.status_code == HTTP_204_NO_CONTENT

    # And the developer is archived in the database
    db_developer = await Developer.get(id=new_developer.id)
    assert db_developer.is_archived
    assert db_developer.archive_date is not None


async def test_new_api_key(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_global_admin: Developer,
    developer_factory: Callable[..., Developer],
) -> None:
    """Verify the admin can generate a new API key for a Developer."""
    # Given a developer with an existing key
    new_developer = await developer_factory()
    original_hashed_api_key = new_developer.hashed_api_key
    original_api_key_fingerprint = new_developer.api_key_fingerprint

    # When the admin generates a new API key
    response = await client.post(
        build_url(GlobalAdmin.DEVELOPER_NEW_KEY, developer_id=new_developer.id),
        headers=token_global_admin,
    )

    # Then the response is successful
    json_data = response.json()
    assert response.status_code == HTTP_201_CREATED

    assert json_data["api_key"] is not None
    assert json_data["username"] == new_developer.username
    assert json_data["email"] == new_developer.email
    assert json_data["date_created"] is not None
    assert json_data["date_modified"] is not None
    assert json_data["is_global_admin"] == str(new_developer.is_global_admin)

    # And the key is updated in the database
    db_developer = await Developer.get(id=new_developer.id)
    assert db_developer.key_generated is not None
    assert db_developer.key_generated.strftime("%Y-%m-%dT%H:%M:%SZ") == json_data["key_generated"]
    assert db_developer.hashed_api_key is not None
    assert db_developer.api_key_fingerprint is not None
    assert db_developer.hashed_api_key != original_hashed_api_key
    assert db_developer.api_key_fingerprint != original_api_key_fingerprint
    assert "companies" in json_data
    assert isinstance(json_data["companies"], list)
