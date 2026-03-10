"""User registration and account management API."""

from __future__ import annotations

from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import post

from vapi.db.models import Company, User  # noqa: TC001
from vapi.domain import deps, hooks, urls
from vapi.domain.services import UserService
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import docs, dto


class UserRegistrationController(Controller):
    """User registration and account management controller."""

    tags = [APITags.USERS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
    }
    guards = [developer_company_user_guard]
    return_dto = dto.ReturnUserDTO

    @post(
        path=urls.Users.REGISTER,
        summary="Register user",
        operation_id="registerUser",
        description=docs.REGISTER_USER_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def register_user(self, data: dto.UserRegisterDTO, company: Company) -> User:
        """Register a new user with the UNAPPROVED role."""
        service = UserService()
        return await service.register_user(company=company, data=data)

    @post(
        path=urls.Users.MERGE,
        summary="Merge users",
        operation_id="mergeUsers",
        description=docs.MERGE_USERS_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def merge_users(self, data: dto.UserMergeDTO, company: Company) -> User:
        """Merge an UNAPPROVED user into an existing primary user."""
        primary_user = await deps.provide_user_by_id_and_company(
            user_id=data.primary_user_id, company=company
        )
        secondary_user = await deps.provide_user_by_id_and_company(
            user_id=data.secondary_user_id, company=company
        )
        service = UserService()
        return await service.merge_users(
            primary_user=primary_user,
            secondary_user=secondary_user,
            company=company,
            requesting_user_id=data.requesting_user_id,
        )
