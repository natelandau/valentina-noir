"""Company API."""

import logging
from uuid import UUID

import msgspec
from litestar import Request
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from tortoise.transactions import in_transaction

from vapi.constants import CompanyPermission, UserRole
from vapi.db.sql_models.company import Company, CompanySettings
from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.db.sql_models.user import User
from vapi.domain import deps, urls
from vapi.domain.handlers import archive_company
from vapi.domain.paginator import Limit, Offset, OffsetPagination
from vapi.domain.services import CompanyService
from vapi.domain.services.company_svc import annotate_company_counts
from vapi.lib.exceptions import NotFoundError
from vapi.lib.guards import (
    developer_company_admin_guard,
    developer_company_owner_guard,
    developer_company_user_guard,
)
from vapi.lib.patch import save_active_patch
from vapi.openapi.tags import APITags

from . import docs
from .dto import (
    CompanyCreate,
    CompanyPatch,
    CompanyPermissionRequest,
    CompanyPermissionResponse,
    CompanyResponse,
    NewCompanyCreateResponse,
    UserResponse,
)

logger = logging.getLogger("vapi")


class CompanyController(Controller):
    """Company controller."""

    tags = [APITags.COMPANIES.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "requesting_developer": Provide(deps.provide_developer_from_request),
    }

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
        limit: Limit = 10,
        offset: Offset = 0,
        requesting_developer: Developer,
    ) -> OffsetPagination[CompanyResponse]:
        """List all companies visible to the requesting developer."""
        service = CompanyService()
        count, companies = await service.list_companies(
            requesting_developer=requesting_developer,
            limit=limit,
            offset=offset,
        )
        return OffsetPagination(
            items=[CompanyResponse.from_model(c) for c in companies],
            limit=limit,
            offset=offset,
            total=count,
        )

    @get(
        path=urls.Companies.DETAIL,
        summary="Get company",
        operation_id="getCompany",
        description=docs.GET_COMPANY_DESCRIPTION,
        guards=[developer_company_user_guard],
        cache=True,
    )
    async def get_company(self, *, company_id: UUID) -> CompanyResponse:
        """Retrieve a company by ID."""
        company = await annotate_company_counts(
            Company.filter(id=company_id, is_archived=False).prefetch_related("settings")
        ).first()
        if not company:
            raise NotFoundError(detail="Company not found")
        return CompanyResponse.from_model(company)

    @post(
        path=urls.Companies.CREATE,
        summary="Create company",
        operation_id="createCompany",
        description=docs.CREATE_COMPANY_DESCRIPTION,
    )
    async def create_company(
        self, request: Request, requesting_developer: Developer, data: CompanyCreate
    ) -> NewCompanyCreateResponse:
        """Create a company with an admin user and owner permission for the requesting developer."""
        # Every company must have a settings row; reads assume it exists.
        async with in_transaction():
            company = await Company.create(
                name=data.name,
                description=data.description,
                email=data.email,
            )

            settings_kwargs = (
                msgspec.structs.asdict(data.settings) if data.settings is not None else {}
            )
            await CompanySettings.create(company=company, **settings_kwargs)

            await DeveloperCompanyPermission.create(
                developer_id=requesting_developer.id,
                company=company,
                permission=CompanyPermission.OWNER,
            )

            admin_user = await User.create(
                username=requesting_developer.username,
                email=requesting_developer.email,
                email_trusted=True,
                role=UserRole.ADMIN,
                company=company,
            )

        company = await annotate_company_counts(
            Company.filter(id=company.id).prefetch_related("settings")
        ).first()
        if not company:
            raise NotFoundError(detail="Company not found")
        request.state.audit_description = f"Create company '{company.name}'"

        return NewCompanyCreateResponse(
            company=CompanyResponse.from_model(company),
            admin_user=UserResponse.from_model(admin_user),
        )

    @patch(
        path=urls.Companies.UPDATE,
        summary="Update company",
        operation_id="updateCompany",
        description=docs.UPDATE_COMPANY_DESCRIPTION,
        guards=[developer_company_admin_guard],
    )
    async def update_company(
        self, request: Request, company: Company, data: CompanyPatch
    ) -> CompanyResponse:
        """Update a company's fields, applying only the provided values."""
        # One transaction so a failed settings update also rolls back the company edits
        async with in_transaction():
            changes = await save_active_patch(
                company, data, label="Company", exclude=frozenset({"settings"})
            )

            if not isinstance(data.settings, msgspec.UnsetType):
                settings = await CompanySettings.filter(company=company).first()
                if settings is not None:
                    settings_changes = await CompanyService().update_settings(
                        settings=settings, patch=data.settings
                    )
                    changes.update(settings_changes)

        request.state.audit_changes = changes

        updated_company = await annotate_company_counts(
            Company.filter(id=company.id).prefetch_related("settings")
        ).first()
        if not updated_company:
            raise NotFoundError(detail="Company not found")

        request.state.audit_description = f"Update company '{updated_company.name}'"
        return CompanyResponse.from_model(updated_company)

    @delete(
        path=urls.Companies.DELETE,
        summary="Delete company",
        operation_id="deleteCompany",
        description=docs.DELETE_COMPANY_DESCRIPTION,
        guards=[developer_company_owner_guard],
    )
    async def delete_company(self, request: Request, company: Company) -> None:
        """Soft-delete a company and cascade the archive to its entire tenant."""
        await archive_company(company=company)
        request.state.audit_description = f"Delete company '{company.name}'"

    @post(
        path=urls.Companies.DEVELOPER_ACCESS,
        summary="Grant developer access",
        operation_id="addDeveloperToCompany",
        description=docs.DEVELOPER_ACCESS_DESCRIPTION,
        guards=[developer_company_owner_guard],
    )
    async def developer_company_permissions(
        self,
        request: Request,
        company: Company,
        requesting_developer: Developer,
        data: CompanyPermissionRequest,
    ) -> CompanyPermissionResponse:
        """Add, update, or revoke a developer's permission level for a company."""
        service = CompanyService()
        perm = await service.control_company_permissions(
            company=company,
            requesting_developer=requesting_developer,
            target_developer_id=data.developer_id,
            new_permission=data.permission,
        )
        request.state.audit_description = f"Grant {data.permission.value} permission to developer {data.developer_id} for company '{company.name}'"
        return CompanyPermissionResponse.from_model(perm)
