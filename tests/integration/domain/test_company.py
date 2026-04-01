"""Test company controller (Tortoise ORM)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
)

from vapi.constants import CompanyPermission
from vapi.db.sql_models.company import Company as PgCompany
from vapi.db.sql_models.company import CompanySettings as PgCompanySettings
from vapi.db.sql_models.developer import Developer as PgDeveloper
from vapi.db.sql_models.developer import DeveloperCompanyPermission
from vapi.domain.urls import Companies

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient


pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("neutralize_after_response_hook")]


class TestCompanyCRUD:
    """Test company CRUD operations for the controller."""

    async def test_list_companies(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: PgDeveloper,
    ) -> None:
        """Verify listing companies returns paginated results."""
        # Given a company the developer has access to (created by pg_mirror fixtures)

        # When we list companies
        response = await client.get(build_url(Companies.LIST), headers=token_company_user)

        # Then the response contains the company
        assert response.status_code == HTTP_200_OK
        assert len(response.json()["items"]) >= 1

    async def test_get_company(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: PgDeveloper,
    ) -> None:
        """Verify getting a single company returns correct data."""
        # When we get the company
        response = await client.get(
            build_url(Companies.DETAIL, company_id=pg_mirror_company.id),
            headers=token_company_user,
        )

        # Then the response contains the company detail
        assert response.status_code == HTTP_200_OK
        assert response.json()["id"] == str(pg_mirror_company.id)

    async def test_create_company(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: PgDeveloper,
    ) -> None:
        """Verify creating a company returns company and admin user."""
        # Given a new company to create
        body = {"name": "Test Company", "description": "Test Description", "email": "test@test.com"}

        # When we create the company
        response = await client.post(
            build_url(Companies.CREATE), headers=token_company_user, json=body
        )

        # Then the response is correct
        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        assert data["company"]["name"] == "Test Company"
        assert data["company"]["description"] == "Test Description"
        assert data["company"]["email"] == "test@test.com"
        assert data["admin_user"]["username"] == pg_mirror_company_user.username
        assert data["admin_user"]["email"] == pg_mirror_company_user.email
        assert data["admin_user"]["role"] == "ADMIN"
        assert data["admin_user"]["company_id"] == data["company"]["id"]

        # Then the company is created in the database
        company_id = data["company"]["id"]
        company = await PgCompany.get(id=company_id)
        assert company.name == "Test Company"
        assert company.description == "Test Description"
        assert company.email == "test@test.com"

        # And the developer is granted OWNER permission for the new company
        perm = await DeveloperCompanyPermission.filter(
            developer_id=pg_mirror_company_user.id,
            company_id=company_id,
        ).first()
        assert perm is not None
        assert perm.permission == CompanyPermission.OWNER

    async def test_patch_company(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: PgDeveloper,
    ) -> None:
        """Verify patching a company updates its name."""
        # Given a new company the developer has ADMIN access to
        new_company = await PgCompany.create(name="original", email="original@test.com")
        await PgCompanySettings.create(company=new_company)
        await DeveloperCompanyPermission.create(
            developer=pg_mirror_company_user,
            company=new_company,
            permission=CompanyPermission.ADMIN,
        )

        # When we patch the company
        response = await client.patch(
            build_url(Companies.UPDATE, company_id=new_company.id),
            headers=token_company_user,
            json={"name": "patched"},
        )

        # Then the response shows the updated name
        assert response.status_code == HTTP_200_OK
        assert response.json()["name"] == "patched"
        assert response.json()["id"] == str(new_company.id)

        # And the company is updated in the database
        await new_company.refresh_from_db()
        assert new_company.name == "patched"

    async def test_patch_company_forbidden_without_admin(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: PgDeveloper,
    ) -> None:
        """Verify patch fails when developer only has USER permission."""
        # Given a company where developer only has USER permission
        new_company = await PgCompany.create(name="original", email="original@test.com")
        await PgCompanySettings.create(company=new_company)
        await DeveloperCompanyPermission.create(
            developer=pg_mirror_company_user,
            company=new_company,
            permission=CompanyPermission.USER,
        )

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
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: PgDeveloper,
    ) -> None:
        """Verify deleting a company soft-deletes it."""
        # Given a company the developer owns
        company = await PgCompany.create(name="to-delete", email="delete@test.com")
        await PgCompanySettings.create(company=company)
        await DeveloperCompanyPermission.create(
            developer=pg_mirror_company_user,
            company=company,
            permission=CompanyPermission.OWNER,
        )

        # When we delete the company
        response = await client.delete(
            build_url(Companies.DELETE, company_id=company.id),
            headers=token_company_user,
        )

        # Then the response is 204
        assert response.status_code == HTTP_204_NO_CONTENT

        # And the company is archived in the database
        await company.refresh_from_db()
        assert company.is_archived is True

    async def test_delete_company_forbidden_without_owner(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: PgDeveloper,
    ) -> None:
        """Verify delete fails when developer only has ADMIN permission."""
        # Given a company where developer only has ADMIN permission
        new_company = await PgCompany.create(name="original", email="original@test.com")
        await PgCompanySettings.create(company=new_company)
        await DeveloperCompanyPermission.create(
            developer=pg_mirror_company_user,
            company=new_company,
            permission=CompanyPermission.ADMIN,
        )

        # When we try to delete
        response = await client.delete(
            build_url(Companies.DELETE, company_id=new_company.id),
            headers=token_company_user,
        )

        # Then the guard blocks us
        assert response.status_code == HTTP_403_FORBIDDEN


class TestCompanyPermissions:
    """Test company permissions."""

    async def test_control_company_permissions(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_owner: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_owner: PgDeveloper,
        pg_developer_factory: Callable,
    ) -> None:
        """Verify granting developer access to a company."""
        # Given a new developer with no company access
        new_developer = await pg_developer_factory(username="new-dev", email="new@test.com")

        # When we grant the developer USER permission
        response = await client.post(
            build_url(Companies.DEVELOPER_ACCESS, company_id=pg_mirror_company.id),
            headers=token_company_owner,
            json={
                "developer_id": str(new_developer.id),
                "permission": CompanyPermission.USER.name,
            },
        )

        # Then the response shows the permission
        assert response.status_code == HTTP_201_CREATED
        assert response.json()["company_id"] == str(pg_mirror_company.id)
        assert response.json()["name"] == pg_mirror_company.name
        assert response.json()["permission"] == CompanyPermission.USER.value

        # And the permission exists in the database
        perm = await DeveloperCompanyPermission.filter(
            developer_id=new_developer.id,
            company_id=pg_mirror_company.id,
        ).first()
        assert perm is not None
        assert perm.permission == CompanyPermission.USER

    async def test_control_company_permissions_forbidden_without_owner(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: PgDeveloper,
    ) -> None:
        """Verify granting permissions fails for non-owner."""
        # When we try to control permissions as a USER
        response = await client.post(
            build_url(Companies.DEVELOPER_ACCESS, company_id=pg_mirror_company.id),
            headers=token_company_user,
            json={
                "developer_id": str(pg_mirror_company_user.id),
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
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: PgDeveloper,
    ) -> None:
        """Verify invalid company settings are rejected."""
        # Given a company the developer owns
        company = await PgCompany.create(name="validation-test", email="valid@test.com")
        await PgCompanySettings.create(company=company)
        await DeveloperCompanyPermission.create(
            developer=pg_mirror_company_user,
            company=company,
            permission=CompanyPermission.OWNER,
        )

        # When we patch with invalid settings
        response = await client.patch(
            build_url(Companies.UPDATE, company_id=company.id),
            headers=token_company_user,
            json={"settings": {"character_autogen_num_choices": 0}},
        )

        # Then the request is rejected
        assert response.status_code == HTTP_400_BAD_REQUEST
