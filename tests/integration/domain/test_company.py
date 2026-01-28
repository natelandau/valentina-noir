"""Test company."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from beanie import PydanticObjectId
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
)

from vapi.constants import CompanyPermission, UserRole
from vapi.db.models import Company, Developer, User
from vapi.db.models.developer import CompanyPermissions
from vapi.domain.services import CompanyService
from vapi.domain.urls import Companies

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient
    from pytest_mock import MockerFixture


pytestmark = pytest.mark.anyio


class TestCompanyCRUD:
    """Test company CRUD operations for the controller."""

    async def test_list_companies(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_user: dict[str, str],
        debug: Callable[[...], None],
        company_factory: Callable[[dict[str, ...]], Company],
    ) -> None:
        """Verify the routes are working for a company user."""
        await company_factory(is_archived=False)

        response = await client.get(build_url(Companies.LIST), headers=token_company_user)
        assert response.status_code == HTTP_200_OK
        assert len(response.json()["items"]) == 1

    async def test_get_company(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_user: dict[str, str],
        base_company: Company,
        mocker: MockerFixture,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the routes are working for a company user."""
        spy = mocker.spy(CompanyService, "can_developer_access_company")
        response = await client.get(
            build_url(Companies.DETAIL, company_id=base_company.id),
            headers=token_company_user,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["id"] == str(base_company.id)
        spy.assert_called_once()

    async def test_create_company(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_user: dict[str, str],
        base_developer_company_user: Developer,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the routes are working for a company user."""
        # Given a new company to create
        body = {"name": "Test Company", "description": "Test Description", "email": "test@test.com"}

        # When we create the company
        response = await client.post(
            build_url(Companies.CREATE), headers=token_company_user, json=body
        )
        assert response.status_code == HTTP_201_CREATED
        # debug(response.json())

        # Then the response is correct
        assert response.json()["company"]["name"] == "Test Company"
        assert response.json()["company"]["description"] == "Test Description"
        assert response.json()["company"]["email"] == "test@test.com"
        assert response.json()["admin_user"]["name"] == base_developer_company_user.username
        assert response.json()["admin_user"]["email"] == base_developer_company_user.email
        assert response.json()["admin_user"]["role"] == "ADMIN"
        assert response.json()["admin_user"]["company_id"] == response.json()["company"]["id"]
        assert response.json()["company"]["user_ids"] == [response.json()["admin_user"]["id"]]

        # Then the company is created in the database
        company_id = response.json()["company"]["id"]
        company = await Company.get(company_id)
        assert company.name == "Test Company"
        assert company.description == "Test Description"
        assert company.email == "test@test.com"

        # And the admin user is created in the database
        admin_user_id = response.json()["admin_user"]["id"]
        admin_user = await User.get(admin_user_id)
        assert admin_user.name == base_developer_company_user.username
        assert admin_user.email == base_developer_company_user.email
        assert admin_user.role == UserRole.ADMIN
        assert str(admin_user.company_id) == company_id

        # And the developer is granted OWNER permission for the company
        await base_developer_company_user.sync()
        new_permission = CompanyPermissions(
            company_id=company_id,
            name=company.name,
            permission=CompanyPermission.OWNER,
        )
        assert new_permission in base_developer_company_user.companies

        # Cleanup
        await company.delete()
        base_developer_company_user.companies.remove(new_permission)
        await base_developer_company_user.save()

    async def test_patch_company(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_developer_company_user: Developer,
        company_factory: Callable[[dict[str, ...]], Company],
        token_company_user: dict[str, str],
        mocker: MockerFixture,
        debug: Callable[[...], None],
    ) -> None:
        """Verify the routes are working for a company user."""
        # Given a new company to patch
        new_company = await company_factory(is_archived=False, name="original")
        permissions = CompanyPermissions(
            company_id=new_company.id,
            name=new_company.name,
            permission=CompanyPermission.ADMIN,
        )
        base_developer_company_user.companies.append(permissions)
        await base_developer_company_user.save()

        # When we patch the company
        response = await client.patch(
            build_url(Companies.UPDATE, company_id=new_company.id),
            headers=token_company_user,
            json={"name": "patched"},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["name"] == "patched"
        assert response.json()["id"] == str(new_company.id)

        # Then the company is patched in the database
        patched_company = await Company.get(new_company.id)
        assert patched_company.name == "patched"

        # Cleanup
        await new_company.delete()
        base_developer_company_user.companies.remove(permissions)
        await base_developer_company_user.save()

    async def test_patch_company_forbidden_without_admin(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_developer_company_user: Developer,
        company_factory: Callable[[dict[str, ...]], Company],
        token_company_user: dict[str, str],
    ) -> None:
        """Verify patch fails when developer only has USER permission."""
        # Given a company where developer only has USER permission (not ADMIN)
        new_company = await company_factory(is_archived=False, name="original")
        permissions = CompanyPermissions(
            company_id=new_company.id,
            name=new_company.name,
            permission=CompanyPermission.USER,  # Only USER, not ADMIN
        )
        base_developer_company_user.companies.append(permissions)
        await base_developer_company_user.save()

        # When we try to patch
        response = await client.patch(
            build_url(Companies.UPDATE, company_id=new_company.id),
            headers=token_company_user,
            json={"name": "patched"},
        )

        # Then the guard blocks us
        assert response.status_code == HTTP_403_FORBIDDEN

    async def test_delete_company(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_developer_company_user: Developer,
        company_factory: Callable[[dict[str, ...]], Company],
        token_company_user: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify the routes are working for a company user."""
        company = await company_factory(is_archived=False, name="original")
        permissions = CompanyPermissions(
            company_id=company.id,
            name=company.name,
            permission=CompanyPermission.OWNER,
        )
        base_developer_company_user.companies.append(permissions)
        await base_developer_company_user.save()

        # When we delete the company
        response = await client.delete(
            build_url(Companies.DELETE, company_id=company.id),
            headers=token_company_user,
        )
        assert response.status_code == HTTP_204_NO_CONTENT

        # Then the company is archived in the database
        await company.sync()
        assert company.is_archived is True

        # Cleanup
        await company.delete()
        base_developer_company_user.companies.remove(permissions)
        await base_developer_company_user.save()

    async def test_delete_company_forbidden_without_owner(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_developer_company_user: Developer,
        company_factory: Callable[[dict[str, ...]], Company],
        token_company_user: dict[str, str],
    ) -> None:
        """Verify delete fails when developer only has USER permission."""
        # Given a company where developer only has USER permission (not OWNER)
        new_company = await company_factory(is_archived=False, name="original")
        permissions = CompanyPermissions(
            company_id=new_company.id,
            name=new_company.name,
            permission=CompanyPermission.ADMIN,
        )
        base_developer_company_user.companies.append(permissions)
        await base_developer_company_user.save()

        # When we try to delete
        response = await client.delete(
            build_url(Companies.DELETE, company_id=new_company.id),
            headers=token_company_user,
        )

        # Then the guard blocks us
        assert response.status_code == HTTP_403_FORBIDDEN

        # Cleanup
        await new_company.delete()
        base_developer_company_user.companies.remove(permissions)
        await base_developer_company_user.save()


class TestCompanyPermissions:
    """Test company permissions."""

    async def test_control_company_permissions(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_owner: dict[str, str],
        developer_factory: Callable[[], Developer],
        base_company: Company,
    ) -> None:
        """Test controlling company permissions."""
        new_developer = await developer_factory(companies=[])

        # When we control the company permissions
        response = await client.post(
            build_url(Companies.DEVELOPER_ACCESS),
            headers=token_company_owner,
            json={"developer_id": str(new_developer.id), "permission": CompanyPermission.USER.name},
        )

        # Then the response is correct
        assert response.status_code == HTTP_201_CREATED
        assert response.json() == CompanyPermissions(
            company_id=base_company.id,
            name=base_company.name,
            permission=CompanyPermission.USER,
        ).model_dump(mode="json")

        # Then the developer is granted USER permission for the company
        await new_developer.sync()
        assert new_developer.companies == [
            CompanyPermissions(
                company_id=base_company.id,
                name=base_company.name,
                permission=CompanyPermission.USER,
            )
        ]

        # Cleanup
        await new_developer.delete()

    async def test_control_company_permissions_forbidden_without_owner(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_user: dict[str, str],
        developer_factory: Callable[[], Developer],
        base_company: Company,
    ) -> None:
        """Test controlling company permissions."""
        # When we control the company permissions
        response = await client.post(
            build_url(Companies.DEVELOPER_ACCESS),
            headers=token_company_user,
            json={
                "developer_id": str(PydanticObjectId()),
                "permission": CompanyPermission.USER.name,
            },
        )

        # Then the guard blocks us
        assert response.status_code == HTTP_403_FORBIDDEN


class TestCompanyValidation:
    """Test company validation."""

    async def test_company_validation(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_owner: dict[str, str],
        base_company: Company,
        debug: Callable[[...], None],
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
