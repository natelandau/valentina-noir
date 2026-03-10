"""User API."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.constants import UserRole
from vapi.db.models import Company, User
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import UserService
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import docs, dto


class UserController(Controller):
    """User controller."""

    tags = [APITags.USERS.name]
    dependencies = {
        "user": Provide(deps.provide_user_by_id_and_company),
        "company": Provide(deps.provide_company_by_id),
        "developer": Provide(deps.provide_developer_from_request),
        "note": Provide(deps.provide_note_by_id),
    }
    guards = [developer_company_user_guard]
    return_dto = dto.ReturnUserDTO

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
    ) -> OffsetPagination[User]:
        """Retrieve users."""
        query = {
            "company_id": company.id,
            "is_archived": False,
        }
        if user_role:
            query["role"] = user_role.name
        if email:
            query["email"] = email

        count = await User.find(query).count()
        users = await User.find(query).skip(offset).limit(limit).to_list()
        return OffsetPagination(items=users, limit=limit, offset=offset, total=count)

    @get(
        path=urls.Users.DETAIL,
        summary="Get user",
        operation_id="getUser",
        description=docs.GET_USER_DESCRIPTION,
        cache=True,
    )
    async def get_user(self, user: User) -> User:
        """Get a user by ID."""
        return user

    @post(
        path=urls.Users.CREATE,
        summary="Create user",
        operation_id="createUser",
        description=docs.CREATE_USER_DESCRIPTION,
        guards=[developer_company_user_guard],
        after_response=hooks.post_data_update_hook,
    )
    async def create_user(self, data: dto.UserPostDTO, company: Company) -> User:
        """Create a new user."""
        service = UserService()
        return await service.create_user(company=company, data=data)

    @patch(
        path=urls.Users.UPDATE,
        summary="Update user",
        operation_id="updateUser",
        description=docs.UPDATE_USER_DESCRIPTION,
        guards=[developer_company_user_guard],
        after_response=hooks.post_data_update_hook,
    )
    async def update_user(self, user: User, data: dto.UserPatchDTO) -> User:
        """Update a user by ID."""
        service = UserService()
        return await service.update_user(user=user, data=data)

    @delete(
        path=urls.Users.DELETE,
        summary="Delete user",
        operation_id="deleteUser",
        description=docs.DELETE_USER_DESCRIPTION,
        guards=[developer_company_user_guard],
        after_response=hooks.post_data_update_hook,
    )
    async def delete_user(
        self, user: User, company: Company, requesting_user_id: PydanticObjectId
    ) -> None:
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
        requesting_user_id: PydanticObjectId,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[User]:
        """Retrieve unapproved users within a company."""
        service = UserService()
        await service.validate_user_can_manage_user(requesting_user_id=requesting_user_id)

        query = {
            "company_id": company.id,
            "is_archived": False,
            "role": UserRole.UNAPPROVED.value,
        }
        count = await User.find(query).count()
        users = await User.find(query).skip(offset).limit(limit).to_list()
        return OffsetPagination(items=users, limit=limit, offset=offset, total=count)

    @post(
        path=urls.Users.APPROVE,
        summary="Approve user",
        operation_id="approveUser",
        description=docs.APPROVE_USER_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def approve_user(self, user: User, data: dto.UserApproveDTO) -> User:
        """Approve an unapproved user and assign a role."""
        service = UserService()
        return await service.approve_user(
            user=user,
            role=data.role,
            requesting_user_id=data.requesting_user_id,
        )

    @post(
        path=urls.Users.DENY,
        summary="Deny user",
        operation_id="denyUser",
        description=docs.DENY_USER_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
        return_dto=None,
    )
    async def deny_user(self, user: User, company: Company, data: dto.UserDenyDTO) -> None:
        """Deny an unapproved user."""
        service = UserService()
        await service.deny_user(
            user=user,
            company=company,
            requesting_user_id=data.requesting_user_id,
        )
