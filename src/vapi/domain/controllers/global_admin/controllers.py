"""Global admin controllers."""

from typing import TYPE_CHECKING, Annotated

import msgspec
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.sql_models.developer import Developer
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import DeveloperService
from vapi.lib.guards import global_admin_guard
from vapi.lib.stores import delete_authentication_cache_for_api_key
from vapi.openapi.tags import APITags

from . import docs
from .dto import AdminDeveloperPatch, DeveloperAdminResponse, DeveloperCreate

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

    @get(
        path=urls.GlobalAdmin.DEVELOPERS,
        summary="List developers",
        operation_id="globalAdminListDevelopers",
        description=docs.LIST_DEVELOPERS_DESCRIPTION,
        cache=True,
    )
    async def list_developers(
        self,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        is_global_admin: Annotated[
            bool | None, Parameter(description="Filter by global admin status.")
        ] = None,
    ) -> OffsetPagination[DeveloperAdminResponse]:
        """List all Developers."""
        qs = Developer.filter(is_archived=False)
        if is_global_admin is not None:
            qs = qs.filter(is_global_admin=is_global_admin)

        count = await qs.count()
        developers = (
            await qs.order_by("username")
            .offset(offset)
            .limit(limit)
            .prefetch_related("permissions__company")
        )

        return OffsetPagination(
            items=[DeveloperAdminResponse.from_model(d) for d in developers],
            limit=limit,
            offset=offset,
            total=count,
        )

    @get(
        path=urls.GlobalAdmin.DEVELOPER_DETAIL,
        summary="Get developer",
        operation_id="globalAdminGetDeveloper",
        description=docs.GET_DEVELOPER_DESCRIPTION,
        cache=True,
    )
    async def retrieve_developer(self, *, developer: Developer) -> DeveloperAdminResponse:
        """Retrieve a Developer by ID."""
        return DeveloperAdminResponse.from_model(developer)

    @post(
        path=urls.GlobalAdmin.DEVELOPER_CREATE,
        summary="Create developer",
        operation_id="globalAdminCreateDeveloper",
        description=docs.CREATE_DEVELOPER_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def create_developer(self, *, data: DeveloperCreate) -> DeveloperAdminResponse:
        """Create a Developer."""
        developer = await Developer.create(
            username=data.username,
            email=data.email,
            is_global_admin=data.is_global_admin,
        )
        developer = (
            await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()
        )
        return DeveloperAdminResponse.from_model(developer)

    @patch(
        path=urls.GlobalAdmin.DEVELOPER_UPDATE,
        summary="Update developer",
        operation_id="globalAdminUpdateDeveloper",
        description=docs.UPDATE_DEVELOPER_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def update_developer(
        self,
        *,
        developer: Developer,
        data: AdminDeveloperPatch,
    ) -> DeveloperAdminResponse:
        """Update a Developer by ID."""
        if not isinstance(data.username, msgspec.UnsetType):
            developer.username = data.username
        if not isinstance(data.email, msgspec.UnsetType):
            developer.email = data.email
        if not isinstance(data.is_global_admin, msgspec.UnsetType):
            developer.is_global_admin = data.is_global_admin

        await developer.save()

        developer = (
            await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()
        )
        return DeveloperAdminResponse.from_model(developer)

    @delete(
        path=urls.GlobalAdmin.DEVELOPER_DELETE,
        summary="Delete developer",
        operation_id="globalAdminDeleteDeveloper",
        description=docs.DELETE_DEVELOPER_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def delete_developer(self, *, developer: Developer, request: "Request") -> None:
        """Delete a Developer by ID."""
        developer.is_archived = True

        await delete_authentication_cache_for_api_key(request)
        await developer.save()

    @post(
        path=urls.GlobalAdmin.DEVELOPER_NEW_KEY,
        summary="Create API key",
        operation_id="globalAdminCreateDeveloperApiKey",
        description=docs.CREATE_API_KEY_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def new_api_key(
        self, *, developer: Developer, request: "Request"
    ) -> dict[str, str | list[dict[str, str]]]:
        """Generate a new API key for a Developer."""
        new_key = await DeveloperService().generate_api_key(developer)

        await delete_authentication_cache_for_api_key(request)

        # Re-fetch with prefetched relations for the companies field
        developer = (
            await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()
        )

        return {
            "id": str(developer.id),
            "username": developer.username,
            "email": developer.email,
            "date_created": developer.date_created.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date_modified": developer.date_modified.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "api_key": new_key,
            "is_global_admin": str(developer.is_global_admin),
            "key_generated": developer.key_generated.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "companies": [
                {
                    "company_id": str(p.company.id),
                    "company_name": p.company.name,
                    "permission": p.permission.value,
                }
                for p in developer.permissions
            ],
        }
