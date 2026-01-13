"""Company API."""

from __future__ import annotations

import logging
from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from beanie.operators import In
from litestar.controller import Controller
from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter
from pydantic import ValidationError as PydanticValidationError

from vapi.db.models import Company, Developer
from vapi.db.models.developer import CompanyPermissions  # noqa: TC001
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CompanyService
from vapi.domain.utils import patch_internal_objects
from vapi.lib.guards import (
    developer_company_admin_guard,
    developer_company_owner_guard,
    developer_company_user_guard,
    global_admin_guard,
)
from vapi.openapi.tags import APITags
from vapi.utils.validation import raise_from_pydantic_validation_error

from . import dto

logger = logging.getLogger("vapi")


class CompanyController(Controller):
    """Company controller."""

    tags = [APITags.COMPANIES.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "developer": Provide(deps.provide_developer_from_request),
    }
    return_dto = dto.CompanyDTO

    @get(
        path=urls.Companies.LIST,
        summary="List companies",
        operation_id="listCompanies",
        description="Retrieve a paginated list of companies. Global admins see all active companies. Regular developers only see companies they have been granted access to.",
        cache=True,
    )
    async def list_companies(
        self,
        *,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        developer: Developer,
    ) -> OffsetPagination[Company]:
        """List all companies."""
        if developer.is_global_admin:
            count = await Company.find(Company.is_archived == False).count()
            companies = (
                await Company.find(Company.is_archived == False).skip(offset).limit(limit).to_list()
            )
            return OffsetPagination(items=companies, limit=limit, offset=offset, total=count)

        company_ids = [perm.company_id for perm in developer.companies]
        count = await Company.find(
            In(Company.id, company_ids),
            Company.is_archived == False,
        ).count()
        companies = await Company.find(
            In(Company.id, company_ids),
            Company.is_archived == False,
        ).to_list()

        return OffsetPagination(items=companies, limit=limit, offset=offset, total=count)

    @get(
        path=urls.Companies.DETAIL,
        summary="Get company",
        operation_id="getCompany",
        description="Retrieve detailed information about a specific company. Requires at least user-level access to the company.",
        guards=[developer_company_user_guard],
        cache=True,
    )
    async def get_company(self, *, company: Company) -> Company:
        """Retrieve a company by ID."""
        return company

    @post(
        path=urls.Companies.CREATE,
        summary="Create company",
        operation_id="createCompany",
        description="Create a new company in the system. Only global administrators can create companies. After creation, use the developer permission endpoints to grant other developers access.",
        guards=[global_admin_guard],
        dto=dto.PostCompanyDTO,
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def create_company(self, data: DTOData[Company]) -> Company:
        """Create a company."""
        try:
            company_data = data.create_instance()
            company = Company(**company_data.model_dump(exclude_unset=True))
            await company.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return company

    @patch(
        path=urls.Companies.UPDATE,
        summary="Update company",
        operation_id="updateCompany",
        description="Modify an existing company's properties. Requires admin-level access to the company. Only include fields that need to be changed; omitted fields remain unchanged.",
        guards=[developer_company_admin_guard],
        dto=dto.PatchCompanyDTO,
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def update_company(self, company: Company, data: DTOData[Company]) -> Company:
        """Update a company."""
        try:
            company, data = await patch_internal_objects(original=company, data=data)
            updated_company = data.update_instance(company)
            await updated_company.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return updated_company

    @delete(
        path=urls.Companies.DELETE,
        summary="Delete company",
        operation_id="deleteCompany",
        description="Delete a company from the system. This is a destructive action and requires owner-level access to the company.",
        guards=[developer_company_owner_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def delete_company(self, company: Company) -> None:
        """Delete a company."""
        company.is_archived = True
        await company.save()

    ### COMPANY PERMISSIONS ###
    @post(
        path=urls.Companies.DEVELOPER_UPDATE,
        summary="Grant developer access",
        operation_id="addDeveloperToCompany",
        description="Add or update a developer's permission level for this company. Requires owner-level access. Valid permission levels are 'user' and 'admin'. You cannot modify your own permissions or grant owner-level access through this endpoint.",
        guards=[developer_company_owner_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def add_developer_to_company(
        self,
        company: Company,
        developer: Developer,
        data: dto.CompanyPermissionsDTO,
    ) -> CompanyPermissions:
        """Add a developer to a company."""
        service = CompanyService()
        return await service.add_developer_to_company(company, developer, data)

    @delete(
        path=urls.Companies.DEVELOPER_DELETE,
        summary="Revoke developer access",
        operation_id="deleteDeveloperFromCompany",
        description="Remove a developer's access to this company entirely. Requires owner-level access. You cannot revoke your own access as the owner.",
        guards=[developer_company_owner_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def delete_developer_from_company(
        self,
        *,
        company: Company,
        developer: Developer,
        developer_id: Annotated[
            PydanticObjectId,
            Parameter(
                title="Developer ID", description="ID of the developer to delete from the company"
            ),
        ],
    ) -> None:
        """Delete a developer from a company."""
        service = CompanyService()
        await service.delete_developer_from_company(company, developer, developer_id)
