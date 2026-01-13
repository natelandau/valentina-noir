"""Test company."""

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

from vapi.constants import (
    DEFAULT_CHARACTER_AUTGEN_NUM_CHOICES,
    CompanyPermission,
    PermissionManageCampaign,
)
from vapi.db.models import Company, Developer
from vapi.db.models.developer import CompanyPermissions
from vapi.domain.urls import Companies

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient


pytestmark = pytest.mark.anyio


async def test_company_admin(
    client: AsyncClient,
    base_company: Company,
    build_url: Callable[[str, Any], str],
    token_company_admin: dict[str, str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the routes are working for a company admin."""
    # create company
    response = await client.post(build_url(Companies.CREATE), headers=token_company_admin)
    assert response.status_code == HTTP_403_FORBIDDEN

    # get company
    response = await client.get(
        build_url(Companies.DETAIL, company_id=base_company.id), headers=token_company_admin
    )
    assert response.status_code == HTTP_200_OK
    assert (
        response.json()["settings"]["character_autogen_num_choices"]
        == DEFAULT_CHARACTER_AUTGEN_NUM_CHOICES
    )

    # patch company
    response = await client.patch(
        build_url(Companies.UPDATE, company_id=base_company.id),
        headers=token_company_admin,
        json={"name": "patched", "settings": {"character_autogen_num_choices": 7}},
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["name"] == "patched"
    assert response.json()["settings"]["character_autogen_num_choices"] == 7

    # patch company
    response = await client.patch(
        build_url(Companies.UPDATE, company_id=base_company.id),
        headers=token_company_admin,
        json={"settings": {"character_autogen_xp_cost": 2}},
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["name"] == "patched"
    assert response.json()["settings"]["character_autogen_num_choices"] == 7
    assert response.json()["settings"]["character_autogen_xp_cost"] == 2

    # delete company
    response = await client.delete(
        build_url(Companies.DELETE, company_id=base_company.id), headers=token_company_admin
    )
    assert response.status_code == HTTP_403_FORBIDDEN


async def test_company_owner(
    client: AsyncClient,
    base_company: Company,
    build_url: Callable[[str, Any], str],
    token_company_owner: dict[str, str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the routes are working for a company owner."""
    # create company
    response = await client.post(build_url(Companies.CREATE), headers=token_company_owner)
    assert response.status_code == HTTP_403_FORBIDDEN

    # get company
    response = await client.get(
        build_url(Companies.DETAIL, company_id=base_company.id), headers=token_company_owner
    )
    assert response.status_code == HTTP_200_OK

    # patch company
    response = await client.patch(
        build_url(Companies.UPDATE, company_id=base_company.id),
        headers=token_company_owner,
        json={"name": "patched"},
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["name"] == "patched"

    # delete company
    response = await client.delete(
        build_url(Companies.DELETE, company_id=base_company.id), headers=token_company_owner
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    # get company fails because it is archived
    response = await client.get(
        build_url(Companies.DETAIL, company_id=base_company.id), headers=token_company_owner
    )
    assert response.status_code == HTTP_404_NOT_FOUND


async def test_company_user(
    client: AsyncClient,
    base_company: Company,
    build_url: Callable[[str, Any], str],
    token_company_user: dict[str, str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the routes are working for a company user."""
    # create company
    response = await client.post(build_url(Companies.CREATE), headers=token_company_user)
    assert response.status_code == HTTP_403_FORBIDDEN

    # get company
    response = await client.get(
        build_url(Companies.DETAIL, company_id=base_company.id), headers=token_company_user
    )
    assert response.status_code == HTTP_200_OK

    # patch company
    response = await client.patch(
        build_url(Companies.UPDATE, company_id=base_company.id),
        headers=token_company_user,
        json={"name": "patched"},
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    # delete company
    response = await client.delete(
        build_url(Companies.DELETE, company_id=base_company.id), headers=token_company_user
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    # get company fails because it is archived
    response = await client.get(
        build_url(Companies.DETAIL, company_id=base_company.id), headers=token_company_user
    )
    assert response.status_code == HTTP_200_OK


async def test_company_global_admin(
    client: AsyncClient,
    build_url: Callable[[str, Any], str],
    token_global_admin: dict[str, str],
    base_company: Company,
    debug: Callable[[Any], None],
) -> None:
    """Verify the routes are working for a global admin."""
    # create company
    response = await client.post(
        build_url(Companies.CREATE),
        headers=token_global_admin,
        json={"name": "Test Company", "description": "Test Description", "email": "test@test.com"},
    )
    assert response.status_code == HTTP_201_CREATED
    company_id = response.json()["id"]

    # get company
    response = await client.get(
        build_url(Companies.DETAIL, company_id=company_id), headers=token_global_admin
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["settings"]["permission_manage_campaign"] == "UNRESTRICTED"

    # patch company
    response = await client.patch(
        build_url(Companies.UPDATE, company_id=company_id),
        headers=token_global_admin,
        json={
            "name": "Test Company patched",
            "settings": {"permission_manage_campaign": "STORYTELLER"},
        },
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["name"] == "Test Company patched"
    assert response.json()["settings"]["permission_manage_campaign"] == "STORYTELLER"
    created_company = await Company.get(company_id)
    assert (
        created_company.settings.permission_manage_campaign == PermissionManageCampaign.STORYTELLER
    )
    assert created_company.name == "Test Company patched"

    # list companies
    response = await client.get(build_url(Companies.LIST), headers=token_global_admin)
    assert response.status_code == HTTP_200_OK
    assert len(response.json()["items"]) == 2

    # delete company
    response = await client.delete(
        build_url(Companies.DELETE, company_id=company_id), headers=token_global_admin
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    # get company fails because it is archived
    response = await client.get(
        build_url(Companies.DETAIL, company_id=company_id), headers=token_global_admin
    )
    assert response.status_code == HTTP_404_NOT_FOUND

    # list companies does not return the company b/c the cache is deleted
    response = await client.get(build_url(Companies.LIST), headers=token_global_admin)
    assert response.status_code == HTTP_200_OK
    assert len(response.json()["items"]) == 1


async def test_list_companies(
    client: AsyncClient,
    build_url: Callable[[str, Any], str],
    token_company_user: dict[str, str],
    debug: Callable[[Any], None],
    company_factory: Callable[[dict[str, Any]], Company],
) -> None:
    """Verify the routes are working for a company user."""
    await company_factory(is_archived=False)

    response = await client.get(build_url(Companies.LIST), headers=token_company_user)
    assert response.status_code == HTTP_200_OK
    assert len(response.json()["items"]) == 1


class TestCompanyPermissions:
    """Test company permissions."""

    async def test_add_company_permission(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_owner: dict[str, str],
        developer_factory: Callable[[], Developer],
        base_company: Company,
        debug: Callable[[Any], None],
    ) -> None:
        """Test adding a company permission."""
        new_developer = await developer_factory()
        new_developer.companies = []
        await new_developer.save()

        response = await client.post(
            build_url(Companies.DEVELOPER_UPDATE),
            headers=token_company_owner,
            json={"developer_id": str(new_developer.id), "permission": CompanyPermission.USER.name},
        )
        assert response.status_code == HTTP_201_CREATED
        assert response.json() == CompanyPermissions(
            company_id=base_company.id,
            name=base_company.name,
            permission=CompanyPermission.USER,
        ).model_dump(mode="json")

        db_developer = await Developer.get(new_developer.id)
        assert db_developer.companies == [
            CompanyPermissions(
                company_id=base_company.id,
                name=base_company.name,
                permission=CompanyPermission.USER,
            )
        ]

        # Cleanup
        await db_developer.delete()

    async def test_delete_company_permission(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_owner: dict[str, str],
        developer_factory: Callable[[], Developer],
        base_company: Company,
        debug: Callable[[Any], None],
    ) -> None:
        """Test deleting a company permission."""
        new_developer = await developer_factory()
        new_developer.companies = [
            CompanyPermissions(
                company_id=base_company.id,
                name=base_company.name,
                permission=CompanyPermission.USER,
            )
        ]
        await new_developer.save()

        response = await client.delete(
            build_url(Companies.DEVELOPER_DELETE),
            headers=token_company_owner,
            params={"developer_id": new_developer.id},
        )
        assert response.status_code == HTTP_204_NO_CONTENT

        await new_developer.sync()
        assert new_developer.companies == []

        # Cleanup
        await new_developer.delete()


class TestCompanyValidation:
    """Test company validation."""

    async def test_company_validation(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_owner: dict[str, str],
        base_company: Company,
        debug: Callable[[Any], None],
    ) -> None:
        """Test company validation."""
        response = await client.patch(
            build_url(Companies.UPDATE, company_id=base_company.id),
            headers=token_company_owner,
            json={"settings": {"character_autogen_num_choices": 0}},
        )
        assert response.status_code == HTTP_400_BAD_REQUEST

        # cleanup
        await base_company.delete()
