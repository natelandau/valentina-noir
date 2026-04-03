"""Test company services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from vapi.constants import CompanyPermission
from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.domain.services import CompanyService
from vapi.lib.exceptions import PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.sql_models.company import Company


pytestmark = pytest.mark.anyio


@dataclass
class DevelopersAndCompanies:
    """Developers and companies."""

    global_admin: Developer
    developer_owner: Developer
    developer_admin: Developer
    developer_user: Developer
    company: Company
    other_company: Company


@pytest.fixture
async def developers_and_companies(
    company_factory: Callable[..., Company],
    developer_factory: Callable[..., Developer],
    developer_company_permission_factory: Callable[..., DeveloperCompanyPermission],
) -> DevelopersAndCompanies:
    """Create developers with varying permissions and two companies for permission tests."""
    other_company = await company_factory(name="Other Company", email="other@example.com")
    company = await company_factory(name="Main Company", email="main@example.com")
    await company_factory(name="Archived Company", email="archived@example.com", is_archived=True)

    global_admin = await developer_factory(is_global_admin=True)
    developer_owner = await developer_factory(is_global_admin=False)
    developer_admin = await developer_factory(is_global_admin=False)
    developer_user = await developer_factory(is_global_admin=False)

    await developer_company_permission_factory(
        developer=developer_owner,
        company=company,
        permission=CompanyPermission.OWNER,
    )
    await developer_company_permission_factory(
        developer=developer_admin,
        company=company,
        permission=CompanyPermission.ADMIN,
    )
    await developer_company_permission_factory(
        developer=developer_user,
        company=company,
        permission=CompanyPermission.USER,
    )

    return DevelopersAndCompanies(
        global_admin=global_admin,
        developer_owner=developer_owner,
        developer_admin=developer_admin,
        developer_user=developer_user,
        company=company,
        other_company=other_company,
    )


class TestListCompanies:
    """Test the list_companies method."""

    async def test_list_companies_global_admin(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Verify global admin sees all non-archived companies."""
        # Given objects
        global_admin = developers_and_companies.global_admin
        company = developers_and_companies.company
        other_company = developers_and_companies.other_company

        # When the method is called
        service = CompanyService()
        count, companies = await service.list_companies(global_admin)

        # Then the result should be the correct count and companies
        assert count == 2
        assert {x.id for x in companies} == {company.id, other_company.id}

    async def test_list_companies_developer(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Verify a regular developer only sees companies they have permission for."""
        # Given objects
        developer_user = developers_and_companies.developer_user
        company = developers_and_companies.company

        # When the method is called
        service = CompanyService()
        count, companies = await service.list_companies(developer_user)

        # Then the result should be the correct count and companies
        assert count == 1
        assert {x.id for x in companies} == {company.id}


class TestCanDeveloperAccessCompany:
    """Test the can_developer_access_company method."""

    async def test_can_developer_access_company_global_admin(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Verify global admin bypasses permission checks for any company."""
        # Given objects
        global_admin = developers_and_companies.global_admin
        other_company = developers_and_companies.other_company

        # When the method is called
        service = CompanyService()
        result = await service.can_developer_access_company(
            developer=global_admin, company_id=other_company.id
        )

        # Then the result should be True
        assert result is True

    async def test_can_developer_access_company_developer(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Verify a developer with user permission can access their company."""
        # Given objects
        developer_user = developers_and_companies.developer_user
        company = developers_and_companies.company

        # When the method is called
        service = CompanyService()
        result = await service.can_developer_access_company(
            developer=developer_user, company_id=company.id
        )

        # Then the result should be True
        assert result is True

    async def test_can_developer_access_company_developer_revoked(
        self,
        developers_and_companies: DevelopersAndCompanies,
        developer_company_permission_factory: Callable[..., DeveloperCompanyPermission],
    ) -> None:
        """Verify a developer with revoked permission is denied access."""
        # Given a developer whose permission is revoked
        developer_owner = developers_and_companies.developer_owner
        other_company = developers_and_companies.other_company
        await developer_company_permission_factory(
            developer=developer_owner,
            company=other_company,
            permission=CompanyPermission.REVOKE,
        )

        # When the method is called
        service = CompanyService()
        with pytest.raises(PermissionDeniedError):
            await service.can_developer_access_company(
                developer=developer_owner, company_id=other_company.id
            )

    async def test_can_developer_access_company_no_permission(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Verify a developer with no permission is denied access."""
        # Given objects
        developer_user = developers_and_companies.developer_user
        other_company = developers_and_companies.other_company

        # When the method is called
        service = CompanyService()
        with pytest.raises(PermissionDeniedError):
            await service.can_developer_access_company(
                developer=developer_user, company_id=other_company.id
            )

    @pytest.mark.parametrize(
        ("minimum_permission", "developer_permission", "expected_result"),
        [
            (CompanyPermission.USER, CompanyPermission.USER, True),
            (CompanyPermission.USER, CompanyPermission.ADMIN, True),
            (CompanyPermission.USER, CompanyPermission.OWNER, True),
            (CompanyPermission.USER, "GLOBAL_ADMIN", True),
            (CompanyPermission.ADMIN, CompanyPermission.USER, False),
            (CompanyPermission.ADMIN, CompanyPermission.ADMIN, True),
            (CompanyPermission.ADMIN, CompanyPermission.OWNER, True),
            (CompanyPermission.ADMIN, "GLOBAL_ADMIN", True),
            (CompanyPermission.OWNER, CompanyPermission.USER, False),
            (CompanyPermission.OWNER, CompanyPermission.ADMIN, False),
            (CompanyPermission.OWNER, CompanyPermission.OWNER, True),
            (CompanyPermission.OWNER, "GLOBAL_ADMIN", True),
        ],
    )
    async def test_can_developer_access_company_minimum_permission(
        self,
        developers_and_companies: DevelopersAndCompanies,
        minimum_permission: CompanyPermission,
        developer_permission: CompanyPermission,
        expected_result: bool,
    ) -> None:
        """Verify the correct result when checking minimum permission levels."""
        # Given the correct developer for the test case
        user = (
            developers_and_companies.developer_user
            if developer_permission == CompanyPermission.USER
            else developers_and_companies.developer_admin
            if developer_permission == CompanyPermission.ADMIN
            else developers_and_companies.developer_owner
            if developer_permission == CompanyPermission.OWNER
            else developers_and_companies.global_admin
        )

        # When the method is called
        service = CompanyService()

        if not expected_result:
            with pytest.raises(PermissionDeniedError):
                await service.can_developer_access_company(
                    developer=user,
                    company_id=developers_and_companies.company.id,
                    minimum_permission=minimum_permission,
                )
        else:
            result = await service.can_developer_access_company(
                developer=user,
                company_id=developers_and_companies.company.id,
                minimum_permission=minimum_permission,
            )
            assert result is True


class TestHelperMethods:
    """Test helper methods."""

    async def test__get_developer_permission_found(
        self,
        company_factory: Callable[..., Company],
        developer_factory: Callable[..., Developer],
        developer_company_permission_factory: Callable[..., DeveloperCompanyPermission],
    ) -> None:
        """Verify _get_developer_permission returns a row when one exists."""
        # Given a developer with permission for a company
        developer = await developer_factory()
        company = await company_factory()
        await developer_company_permission_factory(
            developer=developer,
            company=company,
            permission=CompanyPermission.OWNER,
        )

        # When the method is called
        service = CompanyService()
        result = await service._get_developer_permission(
            developer_id=developer.id, company_id=company.id
        )

        # Then the result should be the permission row
        assert result is not None
        assert result.permission == CompanyPermission.OWNER

    async def test__get_developer_permission_not_found(
        self,
        company_factory: Callable[..., Company],
        developer_factory: Callable[..., Developer],
    ) -> None:
        """Verify _get_developer_permission returns None when no row exists."""
        # Given a developer with no permission for the company
        developer = await developer_factory()
        company = await company_factory()

        # When the method is called
        service = CompanyService()
        result = await service._get_developer_permission(
            developer_id=developer.id, company_id=company.id
        )

        # Then the result should be None
        assert result is None

    async def test__count_company_owners(
        self,
        developers_and_companies: DevelopersAndCompanies,
    ) -> None:
        """Verify _count_company_owners returns the correct count of non-admin owners."""
        # When the method is called
        service = CompanyService()
        result = await service._count_company_owners(company_id=developers_and_companies.company.id)

        # Then the result should be 1 owner
        assert result == 1


class TestControlCompanyPermissions:
    """Test the control_company_permissions method."""

    async def test_control_company_permissions_update_success(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Verify an owner can update an existing developer's permission."""
        # Given objects
        developer_owner = developers_and_companies.developer_owner
        developer_user = developers_and_companies.developer_user
        company = developers_and_companies.company

        # When the method is called
        service = CompanyService()
        result = await service.control_company_permissions(
            company=company,
            requesting_developer=developer_owner,
            target_developer_id=developer_user.id,
            new_permission=CompanyPermission.ADMIN,
        )

        # Then the result should have the updated permission
        assert result.permission == CompanyPermission.ADMIN
        assert result.company_id == company.id

        # And the permission row in the DB should be updated
        updated = await DeveloperCompanyPermission.filter(
            developer_id=developer_user.id, company_id=company.id
        ).first()
        assert updated is not None
        assert updated.permission == CompanyPermission.ADMIN

    async def test_control_company_permissions_new_success(
        self,
        developers_and_companies: DevelopersAndCompanies,
        developer_factory: Callable[..., Developer],
    ) -> None:
        """Verify an owner can grant permission to a developer with no existing row."""
        # Given a developer with no permissions
        developer_owner = developers_and_companies.developer_owner
        new_developer = await developer_factory(is_archived=False)
        company = developers_and_companies.company

        # When the method is called
        service = CompanyService()
        result = await service.control_company_permissions(
            company=company,
            requesting_developer=developer_owner,
            target_developer_id=new_developer.id,
            new_permission=CompanyPermission.OWNER,
        )

        # Then the result should have the new permission
        assert result.permission == CompanyPermission.OWNER
        assert result.company_id == company.id

        # And a permission row should exist in the DB
        created = await DeveloperCompanyPermission.filter(
            developer_id=new_developer.id, company_id=company.id
        ).first()
        assert created is not None
        assert created.permission == CompanyPermission.OWNER

    async def test_control_company_permissions_revoke_success(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Verify an owner can revoke a developer's permission."""
        # Given objects
        developer_owner = developers_and_companies.developer_owner
        developer_user = developers_and_companies.developer_user
        company = developers_and_companies.company

        # When the method is called
        service = CompanyService()
        result = await service.control_company_permissions(
            company=company,
            requesting_developer=developer_owner,
            target_developer_id=developer_user.id,
            new_permission=CompanyPermission.REVOKE,
        )

        # Then the result should be a synthetic revoked permission
        assert result.permission == CompanyPermission.REVOKE
        assert result.company_id == company.id

        # And no permission row should exist in the DB
        remaining = await DeveloperCompanyPermission.filter(
            developer_id=developer_user.id, company_id=company.id
        ).first()
        assert remaining is None

    async def test_control_company_permissions_revoke_owner_success(
        self,
        developers_and_companies: DevelopersAndCompanies,
        developer_company_permission_factory: Callable[..., DeveloperCompanyPermission],
    ) -> None:
        """Verify revoking one owner succeeds when another owner still exists."""
        # Given two owners of the same company
        developer_owner = developers_and_companies.developer_owner
        developer_user = developers_and_companies.developer_user
        company = developers_and_companies.company

        # Promote developer_user to owner (now two owners exist)
        perm = await DeveloperCompanyPermission.filter(
            developer_id=developer_user.id, company_id=company.id
        ).first()
        assert perm is not None
        perm.permission = CompanyPermission.OWNER
        await perm.save()

        # When revoking the second owner
        service = CompanyService()
        result = await service.control_company_permissions(
            company=company,
            requesting_developer=developer_owner,
            target_developer_id=developer_user.id,
            new_permission=CompanyPermission.REVOKE,
        )

        # Then the result should be a synthetic revoked permission
        assert result.permission == CompanyPermission.REVOKE

        # And no permission row should remain for that developer
        remaining = await DeveloperCompanyPermission.filter(
            developer_id=developer_user.id, company_id=company.id
        ).first()
        assert remaining is None

    async def test_control_company_permissions_revoke_owner_failure(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Verify revoking the sole owner raises a ValidationError."""
        # Given objects
        developer_owner = developers_and_companies.developer_owner
        company = developers_and_companies.company

        # When the method is called to revoke the sole owner
        service = CompanyService()
        with pytest.raises(ValidationError):
            await service.control_company_permissions(
                company=company,
                requesting_developer=developer_owner,
                target_developer_id=developer_owner.id,
                new_permission=CompanyPermission.ADMIN,
            )

    async def test_control_company_permissions_idempotent(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Verify setting the same permission twice returns the existing row unchanged."""
        # Given objects
        developer_owner = developers_and_companies.developer_owner
        developer_admin = developers_and_companies.developer_admin
        company = developers_and_companies.company

        # When the method is called with the existing permission
        service = CompanyService()
        result = await service.control_company_permissions(
            company=company,
            requesting_developer=developer_owner,
            target_developer_id=developer_admin.id,
            new_permission=CompanyPermission.ADMIN,
        )

        # Then the result should still have the same permission
        assert result.permission == CompanyPermission.ADMIN
        assert result.company_id == company.id
