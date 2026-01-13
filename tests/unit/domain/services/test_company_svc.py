"""Test company services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from beanie import PydanticObjectId

from vapi.constants import CompanyPermission
from vapi.db.models.developer import CompanyPermissions
from vapi.domain.controllers.company.dto import CompanyPermissionsDTO
from vapi.domain.services import CompanyService
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.models import Company, Developer


pytestmark = pytest.mark.anyio


class TestCompanyService:
    """Test the company service."""

    async def test_add_developer_to_company_new(
        self,
        company_factory: Callable[[], Company],
        developer_factory: Callable[[], Developer],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the add_developer_to_company method."""
        # Given objects
        new_company = await company_factory()
        requesting_developer = await developer_factory(
            companies=[
                CompanyPermissions(
                    company_id=new_company.id,
                    name=new_company.name,
                    permission=CompanyPermission.OWNER,
                )
            ]
        )
        new_developer = await developer_factory(companies=[])

        # When the new developer is added to the company
        service = CompanyService()
        result = await service.add_developer_to_company(
            new_company,
            requesting_developer,
            CompanyPermissionsDTO(developer_id=new_developer.id, permission=CompanyPermission.USER),
        )

        # Then the company permissions should be updated on the new developer
        assert result == CompanyPermissions(
            company_id=new_company.id,
            name=new_company.name,
            permission=CompanyPermission.USER,
        )
        await new_developer.sync()
        assert new_developer.companies == [
            CompanyPermissions(
                company_id=new_company.id,
                name=new_company.name,
                permission=CompanyPermission.USER,
            )
        ]

    async def test_add_developer_to_company_idempotent(
        self,
        company_factory: Callable[[], Company],
        developer_factory: Callable[[], Developer],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the add_developer_to_company method is idempotent."""
        # Given objects
        new_company = await company_factory()
        requesting_developer = await developer_factory(
            companies=[
                CompanyPermissions(
                    company_id=new_company.id,
                    name=new_company.name,
                    permission=CompanyPermission.OWNER,
                )
            ]
        )
        new_developer = await developer_factory(
            companies=[
                CompanyPermissions(
                    company_id=new_company.id,
                    name=new_company.name,
                    permission=CompanyPermission.USER,
                )
            ]
        )

        # When the new developer is added to the company
        service = CompanyService()
        result = await service.add_developer_to_company(
            new_company,
            requesting_developer,
            CompanyPermissionsDTO(developer_id=new_developer.id, permission=CompanyPermission.USER),
        )

        # Then the company permissions should be updated on the new developer
        assert result == CompanyPermissions(
            company_id=new_company.id,
            name=new_company.name,
            permission=CompanyPermission.USER,
        )
        await new_developer.sync()
        assert new_developer.companies == [
            CompanyPermissions(
                company_id=new_company.id,
                name=new_company.name,
                permission=CompanyPermission.USER,
            )
        ]

    async def test_add_developer_to_company_update_existing(
        self,
        company_factory: Callable[[], Company],
        developer_factory: Callable[[], Developer],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the add_developer_to_company method is idempotent."""
        # Given objects
        other_company_permission = CompanyPermissions(
            company_id=PydanticObjectId(),
            name="Existing Company",
            permission=CompanyPermission.OWNER,
        )
        new_company = await company_factory()
        requesting_developer = await developer_factory(
            companies=[
                CompanyPermissions(
                    company_id=new_company.id,
                    name=new_company.name,
                    permission=CompanyPermission.OWNER,
                )
            ]
        )
        new_developer = await developer_factory(
            companies=[
                other_company_permission,
                CompanyPermissions(
                    company_id=new_company.id,
                    name=new_company.name,
                    permission=CompanyPermission.USER,
                ),
            ]
        )

        # When the new developer is added to the company
        service = CompanyService()
        result = await service.add_developer_to_company(
            new_company,
            requesting_developer,
            CompanyPermissionsDTO(
                developer_id=new_developer.id, permission=CompanyPermission.ADMIN
            ),
        )

        # Then the company permissions should be updated on the new developer
        assert result == CompanyPermissions(
            company_id=new_company.id,
            name=new_company.name,
            permission=CompanyPermission.ADMIN,
        )
        await new_developer.sync()
        assert new_developer.companies == [
            other_company_permission,
            CompanyPermissions(
                company_id=new_company.id,
                name=new_company.name,
                permission=CompanyPermission.ADMIN,
            ),
        ]

    async def test_add_developer_to_company_owner_permission(
        self,
        company_factory: Callable[[], Company],
        developer_factory: Callable[[], Developer],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the add_developer_to_company method cannot add an owner permission."""
        # Given objects
        new_company = await company_factory()
        requesting_developer = await developer_factory(
            companies=[
                CompanyPermissions(
                    company_id=new_company.id,
                    name=new_company.name,
                    permission=CompanyPermission.OWNER,
                )
            ]
        )
        new_developer = await developer_factory(companies=[])

        # When the new developer is added to the company
        service = CompanyService()
        with pytest.raises(ValidationError):
            await service.add_developer_to_company(
                new_company,
                requesting_developer,
                CompanyPermissionsDTO(
                    developer_id=new_developer.id, permission=CompanyPermission.OWNER
                ),
            )

    async def test_add_developer_to_company_developer_not_found(
        self,
        company_factory: Callable[[], Company],
        developer_factory: Callable[[], Developer],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the add_developer_to_company method raises a ValidationError if the developer is not found."""
        # Given objects
        new_company = await company_factory()
        requesting_developer = await developer_factory(
            companies=[
                CompanyPermissions(
                    company_id=new_company.id,
                    name=new_company.name,
                    permission=CompanyPermission.OWNER,
                )
            ]
        )

        # When the new developer is added to the company
        service = CompanyService()
        with pytest.raises(ValidationError, match=r"Developer.*not found"):
            await service.add_developer_to_company(
                new_company,
                requesting_developer,
                CompanyPermissionsDTO(
                    developer_id=PydanticObjectId(), permission=CompanyPermission.USER
                ),
            )

    async def test_add_developer_to_company_developer_self(
        self,
        company_factory: Callable[[], Company],
        developer_factory: Callable[[], Developer],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the add_developer_to_company method raises a ValidationError if the developer is the same as the requesting developer."""
        # Given objects
        new_company = await company_factory()
        requesting_developer = await developer_factory(
            companies=[
                CompanyPermissions(
                    company_id=new_company.id,
                    name=new_company.name,
                    permission=CompanyPermission.OWNER,
                )
            ]
        )

        # When the new developer is added to the company
        service = CompanyService()
        with pytest.raises(ValidationError):
            await service.add_developer_to_company(
                new_company,
                requesting_developer,
                CompanyPermissionsDTO(
                    developer_id=requesting_developer.id, permission=CompanyPermission.USER
                ),
            )

    async def test_delete_developer_from_company(
        self,
        company_factory: Callable[[], Company],
        developer_factory: Callable[[], Developer],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the delete_developer_from_company method."""
        # Given objects
        other_company_permission = CompanyPermissions(
            company_id=PydanticObjectId(),
            name="Existing Company",
            permission=CompanyPermission.OWNER,
        )
        new_company = await company_factory()
        requesting_developer = await developer_factory(
            companies=[
                CompanyPermissions(
                    company_id=new_company.id,
                    name=new_company.name,
                    permission=CompanyPermission.OWNER,
                ),
            ]
        )
        new_developer = await developer_factory(
            companies=[
                other_company_permission,
                CompanyPermissions(
                    company_id=new_company.id,
                    name=new_company.name,
                    permission=CompanyPermission.USER,
                ),
            ]
        )

        # When the new developer is deleted from the company
        service = CompanyService()
        await service.delete_developer_from_company(
            new_company,
            requesting_developer,
            new_developer.id,
        )

        # Then the company permissions should be updated on the new developer
        await new_developer.sync()
        assert new_developer.companies == [other_company_permission]

    async def test_delete_developer_from_company_developer_not_found(
        self,
        company_factory: Callable[[], Company],
        developer_factory: Callable[[], Developer],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the delete_developer_from_company method raises a ValidationError if the developer is not found."""
        # Given objects
        new_company = await company_factory()
        requesting_developer = await developer_factory(
            companies=[
                CompanyPermissions(
                    company_id=new_company.id,
                    name=new_company.name,
                    permission=CompanyPermission.OWNER,
                )
            ]
        )

        # When the new developer is deleted from the company
        service = CompanyService()
        with pytest.raises(ValidationError, match=r"Developer.*not found"):
            await service.delete_developer_from_company(
                new_company,
                requesting_developer,
                PydanticObjectId(),
            )

    async def test_delete_developer_from_company_developer_self(
        self,
        company_factory: Callable[[], Company],
        developer_factory: Callable[[], Developer],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the delete_developer_from_company method raises a ValidationError if the developer is the same as the requesting developer."""
        # Given objects
        new_company = await company_factory()
        requesting_developer = await developer_factory(
            companies=[
                CompanyPermissions(
                    company_id=new_company.id,
                    name=new_company.name,
                    permission=CompanyPermission.OWNER,
                )
            ]
        )
        await developer_factory(
            companies=[
                CompanyPermissions(
                    company_id=new_company.id,
                    name=new_company.name,
                    permission=CompanyPermission.USER,
                )
            ]
        )

        # When the new developer is deleted from the company
        service = CompanyService()
        with pytest.raises(ValidationError):
            await service.delete_developer_from_company(
                new_company,
                requesting_developer,
                requesting_developer.id,
            )
