"""User API."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.constants import UserRole  # noqa: TC001
from vapi.db.models import Company, User
from vapi.domain import deps, hooks, urls
from vapi.domain.handlers import UserArchiveHandler
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import UserService
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import dto


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
        description="Retrieve a paginated list of users within a company. Optionally filter by user role.",
        cache=True,
    )
    async def list_users(
        self,
        company: Company,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        user_role: UserRole | None = None,
    ) -> OffsetPagination[User]:
        """Retrieve users."""
        query = {
            "company_id": company.id,
            "is_archived": False,
        }
        if user_role:
            query["role"] = user_role.name

        count = await User.find(query).count()
        users = await User.find(query).skip(offset).limit(limit).to_list()
        return OffsetPagination(items=users, limit=limit, offset=offset, total=count)

    @get(
        path=urls.Users.DETAIL,
        summary="Get user",
        operation_id="getUser",
        description="Retrieve detailed information about a specific user including their role and campaign experience.",
        cache=True,
    )
    async def get_user(self, user: User) -> User:
        """Get a user by ID."""
        return user

    @post(
        path=urls.Users.CREATE,
        summary="Create user",
        operation_id="createUser",
        description="Create a new user within a company. The user will be automatically added to the company's user list. Requires admin-level access to the company.\n\nThe Discord profile is optional and is not used to authenticate the user.\n\nOnly users with admin-level access to the company can create new users.",
        guards=[developer_company_user_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def create_user(self, data: dto.UserPostDTO, company: Company) -> User:
        """Create a new user."""
        service = UserService()
        return await service.create_user(company=company, data=data)

    @patch(
        path=urls.Users.UPDATE,
        summary="Update user",
        operation_id="updateUser",
        description="Modify a user's properties. Only include fields that need to be changed.\n\nOnly users with admin-level access to the company can update other users' properties.",
        guards=[developer_company_user_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def update_user(self, user: User, data: dto.UserPatchDTO) -> User:
        """Update a user by ID."""
        service = UserService()
        return await service.update_user(user=user, data=data)

    @delete(
        path=urls.Users.DELETE,
        summary="Delete user",
        operation_id="deleteUser",
        description="Remove a user from the company. The user will be removed from the company's user list. Requires admin-level access to the company.\n\nOnly users with admin-level access to the company can delete other users.",
        guards=[developer_company_user_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
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

        company.user_ids = [x for x in company.user_ids if x != user.id]
        await company.save()

        await UserArchiveHandler(user=user).handle()
