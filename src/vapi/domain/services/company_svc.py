"""Company service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vapi.constants import CompanyPermission
from vapi.db.models.developer import CompanyPermissions, Developer
from vapi.lib.exceptions import ValidationError

from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from beanie import PydanticObjectId

    from vapi.db.models import Company
    from vapi.domain.controllers.company import dto


class CompanyService:
    """Company service."""

    async def add_developer_to_company(
        self, company: Company, requesting_developer: Developer, data: dto.CompanyPermissionsDTO
    ) -> CompanyPermissions:
        """Add a developer to a company."""
        developer_to_add = await GetModelByIdValidationService().get_developer_by_id(
            data.developer_id
        )
        if not developer_to_add:
            raise ValidationError(
                detail="Developer not found",
                invalid_parameters=[{"field": "developer_id", "message": "Developer not found"}],
            )

        if developer_to_add.id == requesting_developer.id:
            raise ValidationError(
                invalid_parameters=[
                    {
                        "field": "developer_id",
                        "message": "You cannot change your own permissions for a company you own",
                    }
                ],
            )

        if data.permission == CompanyPermission.OWNER:
            raise ValidationError(
                invalid_parameters=[
                    {"field": "permission", "message": "You cannot add an owner permission"}
                ],
            )

        company_permission = next(
            filter(lambda x: x.company_id == company.id, developer_to_add.companies), None
        )

        if company_permission and company_permission.permission == data.permission:
            return company_permission

        if company_permission:
            company_permission.permission = data.permission
        else:
            developer_to_add.companies.append(
                CompanyPermissions(
                    company_id=company.id, name=company.name, permission=data.permission
                )
            )
        await developer_to_add.save()
        return next(filter(lambda x: x.company_id == company.id, developer_to_add.companies), None)

    async def delete_developer_from_company(
        self, company: Company, developer: Developer, developer_id: PydanticObjectId
    ) -> None:
        """Delete a developer from a company."""
        if developer_id == developer.id:
            raise ValidationError(
                invalid_parameters=[
                    {
                        "field": "developer_id",
                        "message": "You cannot delete yourself from a company you do own",
                    }
                ],
            )
        developer_to_act_on = await GetModelByIdValidationService().get_developer_by_id(
            developer_id
        )
        developer_to_act_on.companies = [
            x for x in developer_to_act_on.companies if x.company_id != company.id
        ]
        await developer_to_act_on.save()
