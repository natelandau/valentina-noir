"""Test company services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from vapi.constants import CompanyPermission
from vapi.db.models.developer import CompanyPermissions
from vapi.domain.services import CompanyService, GetModelByIdValidationService
from vapi.lib.exceptions import PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

    from vapi.db.models import Company, Developer


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
    base_company: Company,
    developer_factory: Callable[[], Developer],
    company_factory: Callable[[], Company],
) -> DevelopersAndCompanies:
    """Create a developer and a company and delete the base companies."""
    # Delete the base company to control the database state
    await base_company.delete()

    other_company = await company_factory()
    company = await company_factory()
    archived_company = await company_factory(is_archived=True)
    global_admin = await developer_factory(is_global_admin=True)
    developer_owner = await developer_factory(
        is_global_admin=False,
        companies=[
            CompanyPermissions(
                company_id=company.id, name=company.name, permission=CompanyPermission.OWNER
            )
        ],
    )
    developer_admin = await developer_factory(
        is_global_admin=False,
        companies=[
            CompanyPermissions(
                company_id=company.id, name=company.name, permission=CompanyPermission.ADMIN
            )
        ],
    )
    developer_user = await developer_factory(
        is_global_admin=False,
        companies=[
            CompanyPermissions(
                company_id=company.id, name=company.name, permission=CompanyPermission.USER
            )
        ],
    )

    yield DevelopersAndCompanies(
        global_admin=global_admin,
        developer_owner=developer_owner,
        developer_admin=developer_admin,
        developer_user=developer_user,
        company=company,
        other_company=other_company,
    )

    # cleanup
    await global_admin.delete()
    await developer_owner.delete()
    await developer_admin.delete()
    await developer_user.delete()
    await company.delete()
    await other_company.delete()
    await archived_company.delete()


class TestListCompanies:
    """Test the list_companies method."""

    async def test_list_companies_global_admin(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Test the list_companies method for a global admin."""
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
        """Test the list_companies method for a developer with owner permission."""
        # Given objects
        developer_user = developers_and_companies.developer_user
        company = developers_and_companies.company

        # When the method is called
        service = CompanyService()
        count, companies = await service.list_companies(developer_user)

        # Then the result should be the correct count and companies
        assert count == 1
        assert companies == [company]


class TestCanDeveloperAccessCompany:
    """Test the can_developer_access_company method."""

    async def test_can_developer_access_company_global_admin(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Test the can_developer_access_company method for a global admin."""
        # Given objects
        global_admin = developers_and_companies.global_admin
        other_company = developers_and_companies.other_company

        # When the method is called
        service = CompanyService()
        result = service.can_developer_access_company(
            developer=global_admin, company_id=other_company.id
        )

        # Then the result should be True
        assert result is True

    async def test_can_developer_access_company_developer(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Test the can_developer_access_company method for a developer with user permission."""
        # Given objects
        developer_user = developers_and_companies.developer_user
        company = developers_and_companies.company

        # When the method is called
        service = CompanyService()
        result = service.can_developer_access_company(
            developer=developer_user, company_id=company.id
        )

        # Then the result should be True
        assert result is True

    async def test_can_developer_access_company_developer_revoked(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Test the can_developer_access_company method for a developer with revoked permission."""
        # Given objects
        developer_user = developers_and_companies.developer_user
        company = developers_and_companies.company

        developer_user.companies = [
            CompanyPermissions(
                company_id=company.id,
                name=company.name,
                permission=CompanyPermission.REVOKE,
            )
        ]
        await developer_user.save()

        # When the method is called
        service = CompanyService()
        with pytest.raises(PermissionDeniedError):
            service.can_developer_access_company(developer=developer_user, company_id=company.id)

    async def test_can_developer_access_company_no_permission(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Test the can_developer_access_company method for a developer with no permission."""
        # Given objects
        developer_user = developers_and_companies.developer_user
        other_company = developers_and_companies.other_company

        # When the method is called
        service = CompanyService()
        with pytest.raises(PermissionDeniedError):
            service.can_developer_access_company(
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
        """Test the can_developer_access_company method for a developer with admin permission."""
        # Given objects
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
                service.can_developer_access_company(
                    developer=user,
                    company_id=developers_and_companies.company.id,
                    minimum_permission=minimum_permission,
                )
        else:
            result = service.can_developer_access_company(
                developer=user,
                company_id=developers_and_companies.company.id,
                minimum_permission=minimum_permission,
            )
            assert result is True


class TestHelperMethods:
    """Test helper methods."""

    async def test__is_company_in_developer_companies_true(
        self,
        company_factory: Callable[[], Company],
        developer_factory: Callable[[], Developer],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the _is_company_in_developer_companies method."""
        # Given objects
        developer = await developer_factory()
        company = await company_factory()
        developer.companies.append(
            CompanyPermissions(
                company_id=company.id,
                name=company.name,
                permission=CompanyPermission.OWNER,
            )
        )
        await developer.save()

        # When the method is called
        service = CompanyService()
        result = service._is_company_in_developer_companies(
            developer=developer, company_id=company.id
        )

        # Then the result should be True
        assert result is True

    async def test__is_company_in_developer_companies_false(
        self,
        company_factory: Callable[[], Company],
        developer_factory: Callable[[], Developer],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the _is_company_in_developer_companies method."""
        # Given objects
        developer = await developer_factory()
        company = await company_factory()
        developer.companies.append(
            CompanyPermissions(
                company_id=company.id,
                name=company.name,
                permission=CompanyPermission.OWNER,
            )
        )
        await developer.save()
        company2 = await company_factory()

        # When the method is called
        service = CompanyService()
        result = service._is_company_in_developer_companies(
            developer=developer, company_id=company2.id
        )

        # Then the result should be True
        assert result is False

    async def test__get_company_perms_from_developer_true(
        self,
        company_factory: Callable[[], Company],
        developer_factory: Callable[[], Developer],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the _get_company_perms_from_developer method."""
        # Given objects
        developer = await developer_factory()
        company = await company_factory()
        developer.companies.append(
            CompanyPermissions(
                company_id=company.id,
                name=company.name,
                permission=CompanyPermission.OWNER,
            )
        )
        await developer.save()

        # When the method is called
        service = CompanyService()
        result = service._get_company_perms_from_developer(
            developer=developer, company_id=company.id
        )

        # Then the result should be the company permissions
        assert result == CompanyPermissions(
            company_id=company.id,
            name=company.name,
            permission=CompanyPermission.OWNER,
        )

    async def test__get_company_perms_from_developer_false(
        self,
        company_factory: Callable[[], Company],
        developer_factory: Callable[[], Developer],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the _get_company_perms_from_developer method."""
        # Given objects
        developer = await developer_factory()
        company = await company_factory()
        developer.companies.append(
            CompanyPermissions(
                company_id=company.id,
                name=company.name,
                permission=CompanyPermission.OWNER,
            )
        )
        await developer.save()
        company2 = await company_factory()

        # When the method is called
        service = CompanyService()
        result = service._get_company_perms_from_developer(
            developer=developer, company_id=company2.id
        )

        # Then the result should be None
        assert result is None

    async def test__get_all_company_owners(
        self,
        developers_and_companies: DevelopersAndCompanies,
        debug: Callable[[Any], None],
    ) -> None:
        """Test the _get_company_owners method."""
        # When the method is called
        service = CompanyService()
        result = await service._get_all_company_owners(
            company_id=developers_and_companies.company.id
        )

        # Then the result should be the correct owners
        assert result == [developers_and_companies.developer_owner]


class TestControlCompanyPermissions:
    """Test the control_company_permissions method."""

    async def test_control_company_permissions_update_success(
        self, developers_and_companies: DevelopersAndCompanies, mocker: MockerFixture
    ) -> None:
        """Test the control_company_permissions method for a success case."""
        # Given objects
        developer_owner = developers_and_companies.developer_owner
        developer_user = developers_and_companies.developer_user
        company = developers_and_companies.company

        # Create spies
        spy_can_developer_access_company = mocker.spy(
            CompanyService, "can_developer_access_company"
        )
        spy_get_model_by_id = mocker.spy(GetModelByIdValidationService, "get_developer_by_id")

        # When the method is called
        service = CompanyService()
        result = await service.control_company_permissions(
            company=company,
            requesting_developer=developer_owner,
            target_developer_id=developer_user.id,
            new_permission=CompanyPermission.ADMIN,
        )

        # Then the result should be the correct company permissions
        assert result == CompanyPermissions(
            company_id=company.id,
            name=company.name,
            permission=CompanyPermission.ADMIN,
        )

        await developer_user.sync()
        assert developer_user.companies == [
            CompanyPermissions(
                company_id=company.id,
                name=company.name,
                permission=CompanyPermission.ADMIN,
            )
        ]

        # Then the spies should have been called once
        spy_can_developer_access_company.assert_called_once()
        spy_get_model_by_id.assert_called_once()

    async def test_control_company_permissions_new_success(
        self,
        developers_and_companies: DevelopersAndCompanies,
        developer_factory: Callable[[], Developer],
    ) -> None:
        """Test the control_company_permissions method for a new success case."""
        # Given objects
        developer_owner = developers_and_companies.developer_owner
        developer_user = await developer_factory(companies=[], is_archived=False)
        company = developers_and_companies.company

        # When the method is called
        service = CompanyService()
        result = await service.control_company_permissions(
            company=company,
            requesting_developer=developer_owner,
            target_developer_id=developer_user.id,
            new_permission=CompanyPermission.OWNER,
        )

        # Then the result should be the correct company permissions
        assert result == CompanyPermissions(
            company_id=company.id,
            name=company.name,
            permission=CompanyPermission.OWNER,
        )

        await developer_user.sync()
        assert developer_user.companies == [
            CompanyPermissions(
                company_id=company.id,
                name=company.name,
                permission=CompanyPermission.OWNER,
            )
        ]

    async def test_control_company_permissions_revoke_success(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Test the control_company_permissions method for a revoke success case."""
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

        # Then the result should be None
        assert result == CompanyPermissions(
            company_id=company.id,
            name=company.name,
            permission=CompanyPermission.REVOKE,
        )

        await developer_user.sync()
        assert developer_user.companies == []

    async def test_control_company_permissions_revoke_owner_success(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Test the control_company_permissions method for a revoke owner success case."""
        # Given objects
        developer_owner = developers_and_companies.developer_owner
        developer_user = developers_and_companies.developer_user
        company = developers_and_companies.company

        developer_user.companies = [
            CompanyPermissions(
                company_id=company.id,
                name=company.name,
                permission=CompanyPermission.OWNER,
            )
        ]
        await developer_user.save()

        # When the method is called
        service = CompanyService()
        result = await service.control_company_permissions(
            company=company,
            requesting_developer=developer_owner,
            target_developer_id=developer_user.id,
            new_permission=CompanyPermission.REVOKE,
        )

        # Then the result should be None
        assert result == CompanyPermissions(
            company_id=company.id,
            name=company.name,
            permission=CompanyPermission.REVOKE,
        )
        await developer_user.sync()
        assert developer_user.companies == []

    async def test_control_company_permissions_revoke_owner_failure(
        self, developers_and_companies: DevelopersAndCompanies
    ) -> None:
        """Test the control_company_permissions method for a revoke owner failure case."""
        # Given objects
        developer_owner = developers_and_companies.developer_owner
        company = developers_and_companies.company

        # When the method is called
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
        """Test the control_company_permissions method for an idempotent case."""
        # Given objects
        developer_owner = developers_and_companies.developer_owner
        developer_admin = developers_and_companies.developer_admin
        company = developers_and_companies.company

        # When the method is called
        service = CompanyService()
        result = await service.control_company_permissions(
            company=company,
            requesting_developer=developer_owner,
            target_developer_id=developer_admin.id,
            new_permission=CompanyPermission.ADMIN,
        )

        # Then the result should be the correct company permissions
        assert result == CompanyPermissions(
            company_id=company.id,
            name=company.name,
            permission=CompanyPermission.ADMIN,
        )
