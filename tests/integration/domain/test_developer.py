"""Test developer controller (Tortoise ORM)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED

from vapi.db.sql_models.developer import Developer as PgDeveloper
from vapi.domain.urls import Developers

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_developer_me(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, ...], str],
    pg_mirror_global_admin: PgDeveloper,
    pg_mirror_company: ...,
) -> None:
    """Verify the developer me endpoint returns developer with companies."""
    # When we request the current developer
    response = await client.get(build_url(Developers.ME), headers=token_global_admin)

    # Then the response has the developer data
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["id"] == str(pg_mirror_global_admin.id)
    assert data["username"] == pg_mirror_global_admin.username
    assert data["email"] == pg_mirror_global_admin.email
    assert "companies" in data
    assert isinstance(data["companies"], list)


async def test_developer_new_key(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, ...], str],
    pg_mirror_global_admin: PgDeveloper,
    pg_mirror_company: ...,
) -> None:
    """Verify the developer can generate a new API key."""
    # Given the developer's current key state
    db_developer = await PgDeveloper.get(id=pg_mirror_global_admin.id)
    original_hashed_api_key = db_developer.hashed_api_key
    original_api_key_fingerprint = db_developer.api_key_fingerprint

    # When we request a new key
    response = await client.post(
        build_url(Developers.NEW_KEY),
        headers=token_global_admin,
    )

    # Then the response has the new key info
    assert response.status_code == HTTP_201_CREATED
    json_data = response.json()
    assert json_data["api_key"] is not None
    assert json_data["username"] == pg_mirror_global_admin.username
    assert json_data["email"] == pg_mirror_global_admin.email

    # And the key is updated in the database
    db_developer = await PgDeveloper.get(id=pg_mirror_global_admin.id)
    assert db_developer.key_generated is not None
    assert db_developer.key_generated.strftime("%Y-%m-%dT%H:%M:%SZ") == json_data["key_generated"]
    assert db_developer.hashed_api_key is not None
    assert db_developer.api_key_fingerprint is not None
    assert db_developer.hashed_api_key != original_hashed_api_key
    assert db_developer.api_key_fingerprint != original_api_key_fingerprint


async def test_developer_update(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, ...], str],
    pg_mirror_global_admin: PgDeveloper,
    pg_mirror_company: ...,
) -> None:
    """Verify the developer can update their username and email."""
    # When we update the developer's info
    response = await client.patch(
        build_url(Developers.UPDATE),
        headers=token_global_admin,
        json={"username": "updated user", "email": "updated@test.com"},
    )

    # Then the response has the updated info (username is slugified by pre_save signal)
    assert response.status_code == HTTP_200_OK
    assert response.json()["username"] == "updated-user"
    assert response.json()["email"] == "updated@test.com"

    # And the database is updated
    db_developer = await PgDeveloper.get(id=pg_mirror_global_admin.id)
    assert db_developer.username == "updated-user"
    assert db_developer.email == "updated@test.com"
