"""Unapproved user management controller."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get, post
from litestar.params import Parameter

from vapi.db.models import Company, User
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import UserService
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import docs, dto


class UnapprovedUserController(Controller):
    """Manage unapproved users within a company."""

    tags = [APITags.USERS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "developer": Provide(deps.provide_developer_from_request),
    }
    guards = [developer_company_user_guard]
    return_dto = dto.ReturnUserDTO

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
            "role": "UNAPPROVED",
        }
        count = await User.find(query).count()
        users = await User.find(query).skip(offset).limit(limit).to_list()
        return OffsetPagination(items=users, limit=limit, offset=offset, total=count)

    @post(
        path=urls.Users.APPROVE,
        summary="Approve user",
        operation_id="approveUser",
        description=docs.APPROVE_USER_DESCRIPTION,
        dependencies={"user": Provide(deps.provide_user_by_id_and_company)},
        after_response=hooks.post_data_update_hook,
    )
    async def approve_user(self, user: User, company: Company, data: dto.UserApproveDTO) -> User:
        """Approve an unapproved user and assign a role."""
        service = UserService()
        return await service.approve_user(
            user=user,
            company=company,
            role=data.role,
            requesting_user_id=data.requesting_user_id,
        )

    @post(
        path=urls.Users.DENY,
        summary="Deny user",
        operation_id="denyUser",
        description=docs.DENY_USER_DESCRIPTION,
        dependencies={"user": Provide(deps.provide_user_by_id_and_company)},
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
