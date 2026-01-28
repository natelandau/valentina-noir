"""Company API."""

from __future__ import annotations

import logging
from typing import Annotated

from litestar.controller import Controller
from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter
from pydantic import ValidationError as PydanticValidationError

from vapi.constants import CompanyPermission, UserRole
from vapi.db.models import Company, Developer, User
from vapi.db.models.developer import CompanyPermissions
from vapi.domain import deps, hooks, urls
from vapi.domain.handlers import CompanyArchiveHandler
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CompanyService
from vapi.domain.utils import patch_dto_data_internal_objects
from vapi.lib.dto import COMMON_EXCLUDES
from vapi.lib.guards import (
    developer_company_admin_guard,
    developer_company_owner_guard,
    developer_company_user_guard,
)
from vapi.openapi.tags import APITags
from vapi.utils.validation import raise_from_pydantic_validation_error

from . import docs, dto

logger = logging.getLogger("vapi")


class CompanyController(Controller):
    """Company controller."""

    tags = [APITags.COMPANIES.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "requesting_developer": Provide(deps.provide_developer_from_request),
    }
    return_dto = dto.CompanyDTO

    @get(
        path=urls.Companies.LIST,
        summary="List companies",
        operation_id="listCompanies",
        description=docs.LIST_COMPANIES_DESCRIPTION,
        cache=True,
    )
    async def list_companies(
        self,
        *,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        requesting_developer: Developer,
    ) -> OffsetPagination[Company]:
        """List all companies."""
        service = CompanyService()
        count, companies = await service.list_companies(
            requesting_developer=requesting_developer,
            limit=limit,
            offset=offset,
        )

        return OffsetPagination(items=companies, limit=limit, offset=offset, total=count)

    @get(
        path=urls.Companies.DETAIL,
        summary="Get company",
        operation_id="getCompany",
        description=docs.GET_COMPANY_DESCRIPTION,
        guards=[developer_company_user_guard],
        cache=True,
    )
    async def get_company(self, *, requesting_developer: Developer, company: Company) -> Company:
        """Retrieve a company by ID."""
        service = CompanyService()
        service.can_developer_access_company(developer=requesting_developer, company_id=company.id)
        return company

    @post(
        path=urls.Companies.CREATE,
        summary="Create company",
        operation_id="createCompany",
        description=docs.CREATE_COMPANY_DESCRIPTION,
        dto=dto.PostCompanyDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
        return_dto=None,
    )
    async def create_company(
        self, requesting_developer: Developer, data: DTOData[Company]
    ) -> dto.NewCompanyResponseDTO:
        """Create a company."""
        try:
            company_data = data.create_instance()
            company = Company(**company_data.model_dump(exclude_unset=True))
            await company.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        company_permissions = CompanyPermissions(
            company_id=company.id,
            name=company.name,
            permission=CompanyPermission.OWNER,
        )

        requesting_developer.companies.append(company_permissions)
        await requesting_developer.save()

        admin_user = User(
            name=requesting_developer.username,
            email=requesting_developer.email,
            role=UserRole.ADMIN,
            company_id=company.id,
        )
        await admin_user.save()

        company.user_ids.append(admin_user.id)
        await company.save()

        return dto.NewCompanyResponseDTO(
            company=company.model_dump(exclude=COMMON_EXCLUDES, mode="json"),
            admin_user=admin_user.model_dump(
                exclude=COMMON_EXCLUDES | {"discord_profile", "discord_oauth"}, mode="json"
            ),
        )

    @patch(
        path=urls.Companies.UPDATE,
        summary="Update company",
        operation_id="updateCompany",
        description=docs.UPDATE_COMPANY_DESCRIPTION,
        guards=[developer_company_admin_guard],
        dto=dto.PatchCompanyDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def update_company(self, company: Company, data: DTOData[Company]) -> Company:
        """Update a company."""
        try:
            company, data = await patch_dto_data_internal_objects(original=company, data=data)
            updated_company = data.update_instance(company)
            await updated_company.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return updated_company

    @delete(
        path=urls.Companies.DELETE,
        summary="Delete company",
        operation_id="deleteCompany",
        description=docs.DELETE_COMPANY_DESCRIPTION,
        guards=[developer_company_owner_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def delete_company(self, company: Company) -> None:
        """Delete a company."""
        await CompanyArchiveHandler(company=company).handle()

    @post(
        path=urls.Companies.DEVELOPER_ACCESS,
        summary="Grant developer access",
        operation_id="addDeveloperToCompany",
        description=docs.DEVELOPER_ACCESS_DESCRIPTION,
        guards=[developer_company_owner_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def developer_company_permissions(
        self, company: Company, requesting_developer: Developer, data: dto.CompanyPermissionsDTO
    ) -> CompanyPermissions:
        """Add, update, or revoke a developer's permission level for this company."""
        service = CompanyService()
        return await service.control_company_permissions(
            company=company,
            requesting_developer=requesting_developer,
            target_developer_id=data.developer_id,
            new_permission=data.permission,
        )
