"""User API."""

import asyncio
from typing import Annotated
from uuid import UUID

from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.constants import UserRole
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import UserService
from vapi.lib.detail_includes import apply_includes
from vapi.lib.guards import developer_company_user_guard, user_active_guard
from vapi.lib.rate_limit_policies import USER_REGISTRATION_LIMIT
from vapi.openapi.tags import APITags

from . import docs
from .dto import (
    USER_INCLUDE_PREFETCH_MAP,
    UserApprove,
    UserCreate,
    UserDeny,
    UserDetailResponse,
    UserInclude,
    UserMerge,
    UserPatch,
    UserRegister,
    UserResponse,
)


class UserController(Controller):
    """User controller."""

    tags = [APITags.USERS.name]
    dependencies = {
        "user": Provide(deps.provide_user_by_id_and_company),
        "company": Provide(deps.provide_company_by_id),
        "developer": Provide(deps.provide_developer_from_request),
    }
    guards = [developer_company_user_guard, user_active_guard]

    @get(
        path=urls.Users.LIST,
        summary="List users",
        operation_id="listUsers",
        description=docs.LIST_USERS_DESCRIPTION,
        cache=True,
    )
    async def list_users(
        self,
        company: Company,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        user_role: UserRole | None = None,
        email: str | None = None,
    ) -> OffsetPagination[UserResponse]:
        """Retrieve users."""
        qs = User.filter(company_id=company.id, is_archived=False)
        if user_role:
            qs = qs.filter(role=user_role)
        if email:
            qs = qs.filter(email=email)

        count, users = await asyncio.gather(
            qs.count(),
            qs.offset(offset).limit(limit).prefetch_related("campaign_experiences"),
        )

        return OffsetPagination(
            items=[UserResponse.from_model(u) for u in users],
            limit=limit,
            offset=offset,
            total=count,
        )

    @get(
        path=urls.Users.DETAIL,
        summary="Get user",
        operation_id="getUser",
        description=docs.GET_USER_DESCRIPTION,
        cache=True,
    )
    async def get_user(
        self,
        user: User,
        include: list[UserInclude] | None = None,
    ) -> UserDetailResponse:
        """Get a user by ID with optional embedded children."""
        requested = await apply_includes(user, include, USER_INCLUDE_PREFETCH_MAP)
        return UserDetailResponse.from_model(user, requested)

    @post(
        path=urls.Users.CREATE,
        summary="Create user",
        operation_id="createUser",
        description=docs.CREATE_USER_DESCRIPTION,
        guards=[developer_company_user_guard],
        after_response=hooks.post_data_update_hook,
    )
    async def create_user(self, data: UserCreate, company: Company) -> UserResponse:
        """Create a new user."""
        service = UserService()
        user = await service.create_user(company=company, data=data)
        return UserResponse.from_model(user)

    @patch(
        path=urls.Users.UPDATE,
        summary="Update user",
        operation_id="updateUser",
        description=docs.UPDATE_USER_DESCRIPTION,
        guards=[developer_company_user_guard],
        after_response=hooks.post_data_update_hook,
    )
    async def update_user(self, user: User, data: UserPatch) -> UserResponse:
        """Update a user by ID."""
        service = UserService()
        user = await service.update_user(user=user, data=data)
        return UserResponse.from_model(user)

    @delete(
        path=urls.Users.DELETE,
        summary="Delete user",
        operation_id="deleteUser",
        description=docs.DELETE_USER_DESCRIPTION,
        guards=[developer_company_user_guard],
        after_response=hooks.post_data_update_hook,
    )
    async def delete_user(self, user: User, company: Company, requesting_user_id: UUID) -> None:
        """Delete a user by ID."""
        service = UserService()
        await service.validate_user_can_manage_user(
            user_to_manage_id=user.id,
            requesting_user_id=requesting_user_id,
        )
        await service.remove_and_archive_user(user=user, company=company)

    @get(
        path=urls.Users.UNAPPROVED_LIST,
        summary="List unapproved users",
        operation_id="listUnapprovedUsers",
        description=docs.LIST_UNAPPROVED_USERS_DESCRIPTION,
        cache=True,
    )
    async def list_unapproved_users(
        self,
        company: Company,
        requesting_user_id: UUID,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[UserResponse]:
        """Retrieve unapproved users within a company."""
        service = UserService()
        await service.validate_user_can_manage_user(requesting_user_id=requesting_user_id)

        qs = User.filter(company_id=company.id, is_archived=False, role=UserRole.UNAPPROVED)
        count, users = await asyncio.gather(
            qs.count(),
            qs.offset(offset).limit(limit).prefetch_related("campaign_experiences"),
        )

        return OffsetPagination(
            items=[UserResponse.from_model(u) for u in users],
            limit=limit,
            offset=offset,
            total=count,
        )

    @post(
        path=urls.Users.APPROVE,
        summary="Approve user",
        operation_id="approveUser",
        description=docs.APPROVE_USER_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
        opt={"allow_unapproved_user": True},
    )
    async def approve_user(self, user: User, data: UserApprove) -> UserResponse:
        """Approve an unapproved user and assign a role."""
        service = UserService()
        user = await service.approve_user(
            user=user,
            role=UserRole(data.role),
            requesting_user_id=data.requesting_user_id,
        )
        return UserResponse.from_model(user)

    @post(
        path=urls.Users.DENY,
        summary="Deny user",
        operation_id="denyUser",
        description=docs.DENY_USER_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
        opt={"allow_unapproved_user": True},
    )
    async def deny_user(self, user: User, company: Company, data: UserDeny) -> None:
        """Deny an unapproved user."""
        service = UserService()
        await service.deny_user(
            user=user,
            company=company,
            requesting_user_id=data.requesting_user_id,
        )

    @post(
        path=urls.Users.REGISTER,
        summary="Register user",
        operation_id="registerUser",
        description=docs.REGISTER_USER_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
        opt={"rate_limits": [USER_REGISTRATION_LIMIT]},
    )
    async def register_user(self, data: UserRegister, company: Company) -> UserResponse:
        """Register a new user with the UNAPPROVED role."""
        service = UserService()
        user = await service.register_user(company=company, data=data)
        return UserResponse.from_model(user)

    @post(
        path=urls.Users.MERGE,
        summary="Merge users",
        operation_id="mergeUsers",
        description=docs.MERGE_USERS_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def merge_users(self, data: UserMerge, company: Company) -> UserResponse:
        """Merge an UNAPPROVED user into an existing primary user."""
        service = UserService()
        user = await service.merge_users(
            primary_user_id=data.primary_user_id,
            secondary_user_id=data.secondary_user_id,
            company=company,
            requesting_user_id=data.requesting_user_id,
        )
        return UserResponse.from_model(user)
