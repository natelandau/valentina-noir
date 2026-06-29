"""Global-admin user-management controller."""

import asyncio
from typing import Annotated
from uuid import UUID

from litestar import Request
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.constants import UserRole
from vapi.db.sql_models.user import User
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import GlobalAdminUserService
from vapi.domain.services.user_svc import annotate_user_counts
from vapi.lib.exceptions import NotFoundError
from vapi.lib.guards import global_admin_guard
from vapi.openapi.tags import APITags

from . import docs
from .dto import AdminUserCreate, AdminUserPatch, AdminUserResponse


class GlobalAdminUserController(Controller):
    """Manage users across all companies with a global admin API key."""

    tags = [APITags.GLOBAL_ADMIN.name]
    guards = [global_admin_guard]
    dependencies = {"target_user": Provide(deps.provide_admin_user_by_id)}

    @get(
        path=urls.GlobalAdmin.USERS,
        summary="List users",
        operation_id="globalAdminListUsers",
        description=docs.ADMIN_LIST_USERS_DESCRIPTION,
        cache=True,
    )
    async def list_users(
        self,
        company_id: Annotated[UUID | None, Parameter(description="Filter by company.")] = None,
        role: Annotated[UserRole | None, Parameter(description="Filter by role.")] = None,
        email: Annotated[str | None, Parameter(description="Filter by exact email.")] = None,
        is_archived: Annotated[
            bool | None, Parameter(description="Filter by archived state.")
        ] = None,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[AdminUserResponse]:
        """List users across all companies, with optional filters."""
        qs = User.all()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        if role is not None:
            qs = qs.filter(role=role)
        if email is not None:
            qs = qs.filter(email=email)
        if is_archived is not None:
            qs = qs.filter(is_archived=is_archived)

        count, users = await asyncio.gather(
            qs.count(),
            annotate_user_counts(
                qs.order_by("username")
                .offset(offset)
                .limit(limit)
                .prefetch_related("campaign_experiences")
            ),
        )

        return OffsetPagination(
            items=[AdminUserResponse.from_model(u) for u in users],
            limit=limit,
            offset=offset,
            total=count,
        )

    @get(
        path=urls.GlobalAdmin.USER_DETAIL,
        summary="Get user",
        operation_id="globalAdminGetUser",
        description=docs.ADMIN_GET_USER_DESCRIPTION,
        cache=True,
    )
    async def get_user(self, *, target_user: User) -> AdminUserResponse:
        """Retrieve a single user by ID (archived users included)."""
        # Re-fetch annotated by id; no is_archived filter on the user so archived users stay visible.
        user = await annotate_user_counts(
            User.filter(id=target_user.id).prefetch_related("campaign_experiences")
        ).first()
        if not user:
            raise NotFoundError(detail="User not found")
        return AdminUserResponse.from_model(user)

    @post(
        path=urls.GlobalAdmin.USER_CREATE,
        summary="Create user",
        operation_id="globalAdminCreateUser",
        description=docs.ADMIN_CREATE_USER_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def create_user(self, *, data: AdminUserCreate, request: Request) -> AdminUserResponse:
        """Create a user in the company named by company_id in the body."""
        user = await GlobalAdminUserService().create_user(data)
        request.state.audit_description = (
            f"created user {user.username} in company {user.company_id}"  # ty:ignore[unresolved-attribute]
        )
        user = await annotate_user_counts(
            User.filter(id=user.id).prefetch_related("campaign_experiences")
        ).first()
        if not user:
            raise NotFoundError(detail="User not found")
        return AdminUserResponse.from_model(user)

    @patch(
        path=urls.GlobalAdmin.USER_UPDATE,
        summary="Update user",
        operation_id="globalAdminUpdateUser",
        description=docs.ADMIN_UPDATE_USER_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def update_user(
        self, *, target_user: User, data: AdminUserPatch, request: Request
    ) -> AdminUserResponse:
        """Update any user by ID with no role-matrix restrictions."""
        user, changes = await GlobalAdminUserService().update_user(target_user, data)
        request.state.audit_changes = changes
        user = await annotate_user_counts(
            User.filter(id=user.id).prefetch_related("campaign_experiences")
        ).first()
        if not user:
            raise NotFoundError(detail="User not found")

        return AdminUserResponse.from_model(user)

    @delete(
        path=urls.GlobalAdmin.USER_DELETE,
        summary="Delete user",
        operation_id="globalAdminDeleteUser",
        description=docs.ADMIN_DELETE_USER_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def delete_user(self, *, target_user: User, request: Request) -> None:
        """Soft-delete a user by ID."""
        request.state.audit_description = f"archived user {target_user.username}"
        await GlobalAdminUserService().delete_user(target_user)
