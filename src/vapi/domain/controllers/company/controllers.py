"""Company API."""

import logging
from typing import Annotated
from uuid import UUID

import msgspec
from litestar import Request
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.constants import (
    CompanyPermission,
    PermissionManageCampaign,
    PermissionsFreeTraitChanges,
    PermissionsGrantXP,
    PermissionsRecoupXP,
    UserRole,
)
from vapi.db.sql_models.company import Company, CompanySettings
from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.db.sql_models.user import User
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CompanyService
from vapi.domain.services.company_svc import annotate_company_counts
from vapi.lib.exceptions import NotFoundError
from vapi.lib.guards import (
    developer_company_admin_guard,
    developer_company_owner_guard,
    developer_company_user_guard,
)
from vapi.lib.patch import apply_patch
from vapi.openapi.tags import APITags

from . import docs
from .dto import (
    CompanyCreate,
    CompanyPatch,
    CompanyPermissionRequest,
    CompanyPermissionResponse,
    CompanyResponse,
    CompanySettingsPatch,
    NewCompanyCreateResponse,
    UserResponse,
)

logger = logging.getLogger("vapi")


async def _apply_settings_patch(
    settings: CompanySettings, patch: "CompanySettingsPatch"
) -> dict[str, dict[str, object]]:
    """Apply a partial settings patch and return a diff of what changed.

    Skips any field that is UNSET so partial updates don't overwrite unchanged values.
    Returns a dict of changed fields with dotted `settings.` prefix keys for audit logging.

    Args:
        settings: The CompanySettings record to update in-place.
        patch: The incoming patch data containing optional field overrides.

    Returns:
        dict[str, dict[str, object]]: A mapping of `settings.<field>` to `{"old": ..., "new": ...}` for each changed field.
    """
    changes: dict[str, dict[str, object]] = {}

    for field_name, enum_cls in (
        ("character_autogen_xp_cost", None),
        ("character_autogen_num_choices", None),
        ("character_autogen_starting_points", None),
        ("permission_manage_campaign", PermissionManageCampaign),
        ("permission_grant_xp", PermissionsGrantXP),
        ("permission_free_trait_changes", PermissionsFreeTraitChanges),
        ("permission_recoup_xp", PermissionsRecoupXP),
    ):
        value = getattr(patch, field_name)
        if isinstance(value, msgspec.UnsetType):
            continue
        new_value = enum_cls(value) if enum_cls else value
        old = getattr(settings, field_name)
        if old != new_value:
            changes[f"settings.{field_name}"] = {"old": old, "new": new_value}
            setattr(settings, field_name, new_value)

    await settings.save()
    return changes


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
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
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
        after_response=hooks.post_data_update_hook,
    )
    async def create_company(
        self, request: Request, requesting_developer: Developer, data: CompanyCreate
    ) -> NewCompanyCreateResponse:
        """Create a company with an admin user and owner permission for the requesting developer."""
        company = await Company.create(
            name=data.name,
            description=data.description,
            email=data.email,
        )

        settings_kwargs: dict = {}
        if data.settings is not None:
            settings_kwargs = {
                "character_autogen_xp_cost": data.settings.character_autogen_xp_cost,
                "character_autogen_num_choices": data.settings.character_autogen_num_choices,
                "character_autogen_starting_points": data.settings.character_autogen_starting_points,
                "permission_manage_campaign": data.settings.permission_manage_campaign,
                "permission_grant_xp": data.settings.permission_grant_xp,
                "permission_free_trait_changes": data.settings.permission_free_trait_changes,
                "permission_recoup_xp": data.settings.permission_recoup_xp,
            }
        await CompanySettings.create(company=company, **settings_kwargs)

        await DeveloperCompanyPermission.create(
            developer_id=requesting_developer.id,
            company=company,
            permission=CompanyPermission.OWNER,
        )

        admin_user = await User.create(
            username=requesting_developer.username,
            email=requesting_developer.email,
            role=UserRole.ADMIN,
            company=company,
        )

        company = await annotate_company_counts(
            Company.filter(id=company.id).prefetch_related("settings")
        ).first()
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
        after_response=hooks.post_data_update_hook,
    )
    async def update_company(
        self, request: Request, company: Company, data: CompanyPatch
    ) -> CompanyResponse:
        """Update a company's fields, applying only the provided values."""
        changes = apply_patch(company, data, exclude=frozenset({"settings"}))

        if changes:
            await company.save()

        if not isinstance(data.settings, msgspec.UnsetType):
            settings = await CompanySettings.filter(company=company).first()
            if settings is not None:
                settings_changes = await _apply_settings_patch(settings, data.settings)
                changes.update(settings_changes)

        request.state.audit_changes = changes

        company = await annotate_company_counts(
            Company.filter(id=company.id).prefetch_related("settings")
        ).first()
        request.state.audit_description = f"Update company '{company.name}'"
        return CompanyResponse.from_model(company)

    @delete(
        path=urls.Companies.DELETE,
        summary="Delete company",
        operation_id="deleteCompany",
        description=docs.DELETE_COMPANY_DESCRIPTION,
        guards=[developer_company_owner_guard],
        after_response=hooks.post_data_update_hook,
    )
    async def delete_company(self, request: Request, company: Company) -> None:
        """Soft-delete a company by archiving it."""
        company.is_archived = True
        await company.save()
        request.state.audit_description = f"Delete company '{company.name}'"

    @post(
        path=urls.Companies.DEVELOPER_ACCESS,
        summary="Grant developer access",
        operation_id="addDeveloperToCompany",
        description=docs.DEVELOPER_ACCESS_DESCRIPTION,
        guards=[developer_company_owner_guard],
        after_response=hooks.post_data_update_hook,
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
