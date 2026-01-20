"""Global admin controllers."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Annotated

from litestar.controller import Controller
from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter
from pydantic import ValidationError as PydanticValidationError

from vapi.db.models import Developer
from vapi.db.models.developer import CompanyPermissions  # noqa: TC001
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.utils import patch_dto_data_internal_objects
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
        path=urls.GlobalAdmin.DEVELOPERS,
        summary="List developers",
        operation_id="globalAdminListDevelopers",
        description="Retrieve a paginated list of all developer accounts in the system. Requires global admin privileges.",
        cache=True,
    )
    async def list_developers(
        self,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        is_global_admin: Annotated[
            bool | None, Parameter(description="Filter by global admin status.")
        ] = None,
    ) -> OffsetPagination[Developer]:
        """List all Developers."""
        filters = [
            Developer.is_archived == False,
        ]

        if is_global_admin is not None:
            filters.append(Developer.is_global_admin == is_global_admin)

        count = await Developer.find(*filters).count()
        developers = (
            await Developer.find(*filters).sort("username").skip(offset).limit(limit).to_list()
        )

        return OffsetPagination(items=developers, limit=limit, offset=offset, total=count)

    @get(
        path=urls.GlobalAdmin.DEVELOPER_DETAIL,
        summary="Get developer",
        operation_id="globalAdminGetDeveloper",
        description="Retrieve detailed information about a specific developer account. Requires global admin privileges.",
        cache=True,
    )
    async def retrieve_developer(self, *, developer: Developer) -> Developer:
        """Retrieve an Developer by ID. You must be an admin to access this endpoint."""
        return developer

    @post(
        path=urls.GlobalAdmin.DEVELOPER_CREATE,
        summary="Create developer",
        operation_id="globalAdminCreateDeveloper",
        description="Create a new developer account. This creates the account but does not create an API key or grant access to any companies. **Be certain to generate an API key after account creation.**\n\nRequires global admin privileges.",
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
        path=urls.GlobalAdmin.DEVELOPER_UPDATE,
        summary="Update developer",
        operation_id="globalAdminUpdateDeveloper",
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
        developer, data = await patch_dto_data_internal_objects(original=developer, data=data)
        updated_developer = data.update_instance(developer)
        try:
            await updated_developer.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return updated_developer

    @delete(
        path=urls.GlobalAdmin.DEVELOPER_DELETE,
        summary="Delete developer",
        operation_id="globalAdminDeleteDeveloper",
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
        path=urls.GlobalAdmin.DEVELOPER_NEW_KEY,
        summary="Create API key",
        operation_id="globalAdminCreateDeveloperApiKey",
        description="Generate a new API key for a developer. Their current key will be immediately invalidated.\n\n**Be certain to save the api key as it will not be displayed again.**\n\nRequires global admin privileges.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def new_api_key(
        self, *, developer: Developer, request: Request
    ) -> dict[str, str | list[CompanyPermissions] | datetime]:
        """Generate a new API key for an Developer."""
        new_api_key = await developer.generate_api_key()

        await delete_authentication_cache_for_api_key(request)

        return {
            "id": str(developer.id),
            "username": developer.username,
            "email": developer.email,
            "date_created": developer.date_created,
            "date_modified": developer.date_modified,
            "api_key": new_api_key,
            "is_global_admin": str(developer.is_global_admin),
            "key_generated": developer.key_generated.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "companies": developer.companies,
        }
