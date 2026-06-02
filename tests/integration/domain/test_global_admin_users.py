"""Test global-admin user management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from vapi.db.sql_models.user import User
from vapi.domain.urls import GlobalAdmin

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_admin_list_users(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[..., str],
    company_factory: Callable[..., Any],
    user_factory: Callable[..., Any],
) -> None:
    """Verify the admin can list users without an On-Behalf-Of header."""
    # Given a user exists in a company
    company = await company_factory()
    user = await user_factory(company=company)

    # When listing users as a global admin (no On-Behalf-Of header)
    response = await client.get(build_url(GlobalAdmin.USERS), headers=token_global_admin)

    # Then the user is present in the response
    assert response.status_code == HTTP_200_OK
    returned_ids = [item["id"] for item in response.json()["items"]]
    assert str(user.id) in returned_ids


async def test_admin_list_users_filtered_by_company(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[..., str],
    company_factory: Callable[..., Any],
    user_factory: Callable[..., Any],
) -> None:
    """Verify the company_id filter narrows the list to one company."""
    # Given users in two different companies
    company_a = await company_factory()
    company_b = await company_factory()
    user_a = await user_factory(company=company_a)
    user_b = await user_factory(company=company_b)

    # When listing users filtered by company_a
    response = await client.get(
        build_url(GlobalAdmin.USERS),
        headers=token_global_admin,
        params={"company_id": str(company_a.id)},
    )

    # Then only company_a's user is returned
    assert response.status_code == HTTP_200_OK
    returned_ids = [item["id"] for item in response.json()["items"]]
    assert str(user_a.id) in returned_ids
    assert str(user_b.id) not in returned_ids


async def test_admin_get_user(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[..., str],
    company_factory: Callable[..., Any],
    user_factory: Callable[..., Any],
) -> None:
    """Verify the admin can fetch a single user by ID."""
    # Given a user
    company = await company_factory()
    user = await user_factory(company=company)

    # When fetching the user by ID
    response = await client.get(
        build_url(GlobalAdmin.USER_DETAIL, user_id=user.id),
        headers=token_global_admin,
    )

    # Then the user is returned
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == str(user.id)
    assert response.json()["company_id"] == str(company.id)


async def test_admin_get_archived_user_is_visible(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[..., str],
    company_factory: Callable[..., Any],
    user_factory: Callable[..., Any],
) -> None:
    """Verify archived users are visible in the admin domain."""
    # Given an archived user
    company = await company_factory()
    user = await user_factory(company=company, is_archived=True)

    # When fetching the archived user by ID
    response = await client.get(
        build_url(GlobalAdmin.USER_DETAIL, user_id=user.id),
        headers=token_global_admin,
    )

    # Then it is returned (not 404)
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == str(user.id)


async def test_admin_create_user(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[..., str],
    company_factory: Callable[..., Any],
) -> None:
    """Verify the admin can create a user with company_id in the body."""
    # Given a company
    company = await company_factory()

    # When creating a user
    response = await client.post(
        build_url(GlobalAdmin.USER_CREATE),
        headers=token_global_admin,
        json={
            "company_id": str(company.id),
            "username": "new-admin-user",
            "email": "new-admin-user@example.com",
            "role": "PLAYER",
        },
    )

    # Then the user is created in that company
    assert response.status_code == HTTP_201_CREATED
    data = response.json()
    assert data["username"] == "new-admin-user"
    assert data["company_id"] == str(company.id)
    db_user = await User.get(id=data["id"])
    assert db_user.email == "new-admin-user@example.com"


async def test_admin_create_user_rejects_unapproved_role(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[..., str],
    company_factory: Callable[..., Any],
) -> None:
    """Verify creating a user with role UNAPPROVED is rejected."""
    # Given a company
    company = await company_factory()

    # When creating a user with role UNAPPROVED
    response = await client.post(
        build_url(GlobalAdmin.USER_CREATE),
        headers=token_global_admin,
        json={
            "company_id": str(company.id),
            "username": "bad-role-user",
            "email": "bad-role-user@example.com",
            "role": "UNAPPROVED",
        },
    )

    # Then the request is rejected (service-level ValidationError -> 400)
    assert response.status_code == HTTP_400_BAD_REQUEST


async def test_admin_update_user_role(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[..., str],
    company_factory: Callable[..., Any],
    user_factory: Callable[..., Any],
) -> None:
    """Verify the admin can change a user's role with no matrix restrictions."""
    # Given a PLAYER user
    company = await company_factory()
    user = await user_factory(company=company, role="PLAYER")

    # When patching the role to ADMIN
    response = await client.patch(
        build_url(GlobalAdmin.USER_UPDATE, user_id=user.id),
        headers=token_global_admin,
        json={"role": "ADMIN"},
    )

    # Then the role is updated and persisted
    assert response.status_code == HTTP_200_OK
    assert response.json()["role"] == "ADMIN"
    db_user = await User.get(id=user.id)
    assert db_user.role == "ADMIN"


async def test_admin_restore_archived_user(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[..., str],
    company_factory: Callable[..., Any],
    user_factory: Callable[..., Any],
) -> None:
    """Verify patching is_archived=false restores a soft-deleted user."""
    # Given an archived user
    company = await company_factory()
    user = await user_factory(company=company, is_archived=True)

    # When patching is_archived to false
    response = await client.patch(
        build_url(GlobalAdmin.USER_UPDATE, user_id=user.id),
        headers=token_global_admin,
        json={"is_archived": False},
    )

    # Then the user is restored
    assert response.status_code == HTTP_200_OK
    db_user = await User.get(id=user.id)
    assert db_user.is_archived is False


async def test_admin_delete_user_soft_deletes(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[..., str],
    company_factory: Callable[..., Any],
    user_factory: Callable[..., Any],
) -> None:
    """Verify delete soft-deletes the user."""
    # Given a user
    company = await company_factory()
    user = await user_factory(company=company)

    # When deleting the user
    response = await client.delete(
        build_url(GlobalAdmin.USER_DELETE, user_id=user.id),
        headers=token_global_admin,
    )

    # Then it is archived, not hard-deleted
    assert response.status_code == HTTP_204_NO_CONTENT
    db_user = await User.get(id=user.id)
    assert db_user.is_archived is True


async def test_admin_get_unknown_user_404(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[..., str],
) -> None:
    """Verify an unknown user ID returns 404."""
    # Given a random UUID that does not exist
    from uuid import uuid4

    # When fetching it
    response = await client.get(
        build_url(GlobalAdmin.USER_DETAIL, user_id=uuid4()),
        headers=token_global_admin,
    )

    # Then 404 is returned
    assert response.status_code == HTTP_404_NOT_FOUND


async def test_non_admin_key_forbidden(
    client: AsyncClient,
    token_company_owner: dict[str, str],
    build_url: Callable[..., str],
) -> None:
    """Verify a non-global-admin key is rejected by the guard."""
    # Given a company-owner (non-global-admin) developer key
    # When listing admin users
    response = await client.get(build_url(GlobalAdmin.USERS), headers=token_company_owner)

    # Then access is forbidden
    assert response.status_code == HTTP_403_FORBIDDEN


async def test_admin_list_users_filtered_by_archived_state(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[..., str],
    company_factory: Callable[..., Any],
    user_factory: Callable[..., Any],
) -> None:
    """Verify the is_archived filter narrows the list to archived users."""
    # Given an active and an archived user in the same company
    company = await company_factory()
    active_user = await user_factory(company=company)
    archived_user = await user_factory(company=company, is_archived=True)

    # When listing users filtered to archived only, scoped to that company
    response = await client.get(
        build_url(GlobalAdmin.USERS),
        headers=token_global_admin,
        params={"company_id": str(company.id), "is_archived": "true"},
    )

    # Then only the archived user is returned
    assert response.status_code == HTTP_200_OK
    returned_ids = [item["id"] for item in response.json()["items"]]
    assert str(archived_user.id) in returned_ids
    assert str(active_user.id) not in returned_ids
