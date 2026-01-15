"""Developer controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar.controller import Controller
from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter
from litestar.status_codes import HTTP_200_OK
from pydantic import ValidationError as PydanticValidationError

from vapi.constants import CompanyPermission
from vapi.db.models import Company, Developer
from vapi.db.models.developer import CompanyPermissions
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.utils import patch_internal_objects
from vapi.lib.exceptions import ConflictError, ValidationError
from vapi.lib.guards import global_admin_guard
from vapi.lib.stores import delete_authentication_cache_for_api_key
from vapi.openapi.tags import APITags
from vapi.utils.validation import raise_from_pydantic_validation_error

from . import dto

if TYPE_CHECKING:
    from litestar import Request


class GlobalAdminController(Controller):
    """Global admin controller."""

    tags = [APITags.GLOBAL_ADMIN.name]
    guards = [global_admin_guard]
    dependencies = {
        "developer": Provide(deps.provide_developer_by_id),
        "company": Provide(deps.provide_company_by_id),
    }
    return_dto = dto.DeveloperReturnDTO

    @get(
        path=urls.GlobalAdmin.LIST,
        summary="List developers",
        operation_id="listDevelopers",
        description="Retrieve a paginated list of all developer accounts in the system. Requires global admin privileges.",
        cache=True,
    )
    async def list_developers(
        self,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[Developer]:
        """List all Developers."""
        query = {
            "is_archived": False,
        }
        count = await Developer.find(query).count()
        developers = await Developer.find(query).skip(offset).limit(limit).sort("name").to_list()

        return OffsetPagination(items=developers, limit=limit, offset=offset, total=count)

    @get(
        path=urls.GlobalAdmin.DETAIL,
        summary="Get developer",
        operation_id="getDeveloper",
        description="Retrieve detailed information about a specific developer account. Requires global admin privileges.",
        cache=True,
    )
    async def retrieve_developer(self, *, developer: Developer) -> Developer:
        """Retrieve an Developer by ID. You must be an admin to access this endpoint."""
        return developer

    @post(
        path=urls.GlobalAdmin.CREATE,
        summary="Create developer",
        operation_id="createDeveloper",
        description="Create a new developer account. The new developer will receive an API key for authentication. Requires global admin privileges.",
        dto=dto.DeveloperCreateDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def create_developer(self, *, data: DTOData[Developer]) -> Developer:
        """Create an Developer."""
        try:
            developer_data = data.create_instance()
            developer = Developer(**developer_data.model_dump(exclude_unset=True))
            await developer.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return developer

    @patch(
        path=urls.GlobalAdmin.UPDATE,
        summary="Update developer",
        operation_id="updateDeveloper",
        description="Modify a developer account's properties. Only include fields that need to be changed. Requires global admin privileges.",
        dto=dto.DeveloperPatchDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def update_developer(
        self,
        *,
        developer: Developer,
        data: DTOData[Developer],
    ) -> Developer:
        """Update an Developer by ID."""
        developer, data = await patch_internal_objects(original=developer, data=data)
        updated_developer = data.update_instance(developer)
        try:
            await updated_developer.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return updated_developer

    @delete(
        path=urls.GlobalAdmin.DELETE,
        summary="Delete developer",
        operation_id="deleteDeveloper",
        description="Remove a developer account from the system. The developer's API key will be invalidated immediately. Requires global admin privileges.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def delete_developer(self, *, developer: Developer, request: Request) -> None:
        """Delete an Developer by ID."""
        developer.is_archived = True

        await delete_authentication_cache_for_api_key(request)
        await developer.save()

    # ############################# API Key #############################
    @post(
        path=urls.GlobalAdmin.NEW_KEY,
        summary="Regenerate developer API key",
        operation_id="regenerateDeveloperApiKey",
        description="Generate a new API key for a developer. Their current key will be immediately invalidated. Requires global admin privileges.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def new_api_key(self, *, developer: Developer, request: Request) -> dict[str, str]:
        """Generate a new API key for an Developer."""
        new_api_key = await developer.generate_api_key()

        await delete_authentication_cache_for_api_key(request)

        return {
            "id": str(developer.id),
            "username": developer.username,
            "email": developer.email,
            "api_key": new_api_key,
            "is_global_admin": str(developer.is_global_admin),
            "key_generated": developer.key_generated.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    # ############################# Company Permissions #############################
    @post(
        path=urls.GlobalAdmin.COMPANY_PERMISSIONS,
        summary="Grant company access",
        operation_id="addCompanyPermission",
        description="Add a company permission to a developer, allowing them to access company resources. Specify the permission level (user, admin, or owner). Requires global admin privileges.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def add_company(
        self,
        *,
        developer: Developer,
        company: Company,
        permission: Annotated[
            CompanyPermission,
            Parameter(title="Permission", description="Company permission to add to the Developer"),
        ],
    ) -> Developer:
        """Add a company to an Developer."""
        if any(x.company_id == company.id for x in developer.companies):
            raise ConflictError(detail="Company already added to Developer")

        developer.companies.append(
            CompanyPermissions(
                company_id=company.id, name=company.name, permission=CompanyPermission(permission)
            )
        )

        await developer.save()
        return developer

    @patch(
        path=urls.GlobalAdmin.COMPANY_PERMISSIONS,
        summary="Update company permission",
        operation_id="updateCompanyPermission",
        description="Change a developer's permission level for a company they already have access to. Requires global admin privileges.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def update_company_permission(
        self,
        *,
        developer: Developer,
        company: Company,
        permission: Annotated[
            CompanyPermission,
            Parameter(title="Permission", description="Company permission to add to the Developer"),
        ],
    ) -> Developer:
        """Update a company permission for an Developer."""
        if not any(x.company_id == company.id for x in developer.companies):
            raise ValidationError(
                detail="Company not added to Developer",
                invalid_parameters=[
                    {"field": "company_id", "message": "Company not added to Developer"},
                ],
            )

        company_permission = next(x for x in developer.companies if x.company_id == company.id)
        company_permission.permission = CompanyPermission(permission)
        await developer.save()

        return developer

    @delete(
        path=urls.GlobalAdmin.COMPANY_PERMISSIONS,
        summary="Revoke company access",
        operation_id="removeCompanyPermission",
        description="Remove a developer's access to a company entirely. They will no longer be able to access any resources within that company. Requires global admin privileges.",
        status_code=HTTP_200_OK,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def remove_company(
        self,
        *,
        developer: Developer,
        company: Company,
        permission: Annotated[  # noqa: ARG002
            CompanyPermission,
            Parameter(
                title="Permission",
                description="Company permission to remove from the Developer",
            ),
        ],
    ) -> Developer:
        """Remove a company from an Developer."""
        developer.companies = [x for x in developer.companies if x.company_id != company.id]
        await developer.save()
        return developer
