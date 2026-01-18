"""Test Global Admin."""

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_409_CONFLICT,
)

from vapi.constants import CompanyPermission
from vapi.db.models import Company, Developer
from vapi.db.models.developer import CompanyPermissions
from vapi.domain.urls import GlobalAdmin

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_admin_list_developers(
    client: "AsyncClient",
    token_global_admin: dict[str, str],
    base_developer_global_admin: "Developer",
    developer_factory: Callable[[], Developer],
    build_url: Callable[[str, Any], str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the admin can list Developers."""
    for d in await Developer.find(Developer.is_global_admin == False).to_list():
        await d.delete()

    new_developer = await developer_factory()

    response = await client.get(build_url(GlobalAdmin.DEVELOPERS), headers=token_global_admin)
    assert response.status_code == HTTP_200_OK

    json_data = response.json()
    assert len(json_data["items"]) == 2

    # debug(json_data["items"][0])
    assert json_data["items"] == [
        base_developer_global_admin.model_dump(
            mode="json",
            exclude={"is_archived", "archive_date", "api_key_fingerprint", "hashed_api_key"},
        ),
        new_developer.model_dump(
            mode="json",
            exclude={"is_archived", "archive_date", "api_key_fingerprint", "hashed_api_key"},
        ),
    ]

    # Cleanup
    await new_developer.delete()


async def test_get_developer(
    client: "AsyncClient",
    token_global_admin: dict[str, str],
    base_developer_global_admin: "Developer",
    build_url: Callable[[str, Any], str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the admin can get an Developer."""
    response = await client.get(
        build_url(GlobalAdmin.DEVELOPER_DETAIL, developer_id=base_developer_global_admin.id),
        headers=token_global_admin,
    )
    assert response.status_code == HTTP_200_OK
    # debug(response.text)
    assert response.json() == base_developer_global_admin.model_dump(
        exclude={"is_archived", "archive_date", "api_key_fingerprint", "hashed_api_key"},
        mode="json",
    )


async def test_post_developer(
    client: "AsyncClient",
    token_global_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the admin can post an Developer."""
    response = await client.post(
        build_url(GlobalAdmin.DEVELOPER_CREATE),
        headers=token_global_admin,
        json={"username": "test user", "email": "test@test.com", "is_global_admin": False},
    )
    assert response.status_code == HTTP_201_CREATED

    assert response.json()["username"] == "test-user"
    assert response.json()["email"] == "test@test.com"
    assert not response.json()["is_global_admin"]
    assert response.json()["companies"] == []

    db_developer = await Developer.get(response.json()["id"])
    assert db_developer.username == "test-user"
    assert db_developer.email == "test@test.com"
    assert not db_developer.is_global_admin
    assert db_developer.companies == []

    # Cleanuo
    await db_developer.delete()


async def test_patch_developer(
    client: "AsyncClient",
    token_global_admin: dict[str, str],
    developer_factory: Callable[[], Developer],
    build_url: Callable[[str, Any], str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the admin can patch an Developer."""
    new_developer = await developer_factory(username="original")

    response = await client.patch(
        build_url(GlobalAdmin.DEVELOPER_DETAIL, developer_id=new_developer.id),
        headers=token_global_admin,
        json={"username": "patched"},
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["username"] == "patched"
    assert response.json()["email"] == new_developer.email
    assert response.json()["is_global_admin"] == new_developer.is_global_admin
    assert response.json()["companies"] == new_developer.model_dump(mode="json")["companies"]

    db_developer = await Developer.get(new_developer.id)
    assert db_developer.username == "patched"
    assert db_developer.email == new_developer.email
    assert db_developer.is_global_admin == new_developer.is_global_admin
    assert db_developer.companies == new_developer.companies

    # Cleanup
    await db_developer.delete()


async def test_delete_developer(
    client: "AsyncClient",
    token_global_admin: dict[str, str],
    developer_factory: Callable[[], Developer],
    build_url: Callable[[str, Any], str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the admin can delete an Developer."""
    new_developer = await developer_factory()
    response = await client.delete(
        build_url(GlobalAdmin.DEVELOPER_DETAIL, developer_id=new_developer.id),
        headers=token_global_admin,
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    db_developer = await Developer.get(new_developer.id)
    assert db_developer.is_archived
    assert db_developer.archive_date is not None

    # Cleanup
    await db_developer.delete()


async def test_new_api_key(
    client: "AsyncClient",
    token_global_admin: dict[str, str],
    developer_factory: Callable[[], Developer],
    build_url: Callable[[str, Any], str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the admin can generate a new API key for an Developer."""
    # Given a developer
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
    assert datetime.fromisoformat(json_data["date_created"]) == new_developer.date_created
    assert datetime.fromisoformat(json_data["date_modified"]) == new_developer.date_modified
    assert json_data["is_global_admin"] == str(new_developer.is_global_admin)
    assert json_data["companies"] == new_developer.model_dump(mode="json")["companies"]

    db_developer = await Developer.get(new_developer.id)
    assert db_developer.key_generated is not None
    assert db_developer.key_generated.strftime("%Y-%m-%dT%H:%M:%SZ") == json_data["key_generated"]
    assert db_developer.hashed_api_key is not None
    assert db_developer.api_key_fingerprint is not None
    assert db_developer.hashed_api_key != original_hashed_api_key
    assert db_developer.api_key_fingerprint != original_api_key_fingerprint

    # Cleanup
    await new_developer.delete()


async def test_add_company_permission(
    client: "AsyncClient",
    token_global_admin: dict[str, str],
    developer_factory: Callable[[], Developer],
    base_company: Company,
    build_url: Callable[[str, Any], str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the admin can add a company permission to an Developer."""
    new_developer = await developer_factory()
    new_developer.companies = []
    await new_developer.save()

    response = await client.post(
        build_url(
            GlobalAdmin.DEVELOPER_COMPANY_PERMISSIONS,
            developer_id=new_developer.id,
            company_id=base_company.id,
            permission=CompanyPermission.OWNER.name,
        ),
        headers=token_global_admin,
    )
    assert response.status_code == HTTP_201_CREATED
    assert response.json()["companies"] == [
        {
            "company_id": str(base_company.id),
            "name": base_company.name,
            "permission": CompanyPermission.OWNER.name,
        }
    ]

    db_developer = await Developer.get(new_developer.id)
    assert db_developer.companies == [
        CompanyPermissions(
            company_id=base_company.id, name=base_company.name, permission=CompanyPermission.OWNER
        )
    ]

    # Cleanup
    await db_developer.delete()


async def test_add_company_permission_already_exists(
    client: "AsyncClient",
    token_global_admin: dict[str, str],
    base_developer_company_admin: Developer,
    base_company: Company,
    build_url: Callable[[str, Any], str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the admin cannot add a company permission to an Developer that already exists."""
    response = await client.post(
        build_url(
            GlobalAdmin.DEVELOPER_COMPANY_PERMISSIONS,
            developer_id=base_developer_company_admin.id,
            company_id=base_company.id,
            permission=CompanyPermission.OWNER.name,
        ),
        headers=token_global_admin,
    )
    assert response.status_code == HTTP_409_CONFLICT


async def test_update_company_permission(
    client: "AsyncClient",
    token_global_admin: dict[str, str],
    base_developer_company_admin: Developer,
    base_company: Company,
    build_url: Callable[[str, Any], str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the admin can update a company permission for an Developer."""
    response = await client.patch(
        build_url(
            GlobalAdmin.DEVELOPER_COMPANY_PERMISSIONS,
            developer_id=base_developer_company_admin.id,
            company_id=base_company.id,
            permission=CompanyPermission.OWNER.name,
        ),
        headers=token_global_admin,
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["companies"] == [
        {
            "company_id": str(base_company.id),
            "name": base_company.name,
            "permission": CompanyPermission.OWNER.name,
        }
    ]

    db_developer = await Developer.get(base_developer_company_admin.id)
    assert db_developer.companies == [
        CompanyPermissions(
            company_id=base_company.id, name=base_company.name, permission=CompanyPermission.OWNER
        )
    ]

    # Cleanup
    await db_developer.delete()


async def test_remove_company_permission(
    client: "AsyncClient",
    token_global_admin: dict[str, str],
    developer_factory: Callable[[], Developer],
    company_factory: Callable[[], Company],
    build_url: Callable[[str, Any], str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the admin can remove a company permission for an Developer."""
    developer = await developer_factory()
    company1 = await company_factory()
    company2 = await company_factory()
    developer.companies = [
        CompanyPermissions(
            company_id=company1.id, name=company1.name, permission=CompanyPermission.OWNER
        ),
        CompanyPermissions(
            company_id=company2.id, name=company2.name, permission=CompanyPermission.USER
        ),
    ]
    await developer.save()
    ####################################
    response = await client.delete(
        build_url(
            GlobalAdmin.DEVELOPER_COMPANY_PERMISSIONS,
            developer_id=developer.id,
            company_id=company2.id,
            permission=CompanyPermission.USER.name,
        ),
        headers=token_global_admin,
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["companies"] == [
        {
            "company_id": f"{company1.id}",
            "name": company1.name,
            "permission": "OWNER",
        }
    ]

    db_developer = await Developer.get(developer.id)
    assert db_developer.companies == [
        CompanyPermissions(
            company_id=company1.id, name=company1.name, permission=CompanyPermission.OWNER
        )
    ]

    # Cleanup
    await db_developer.delete()
