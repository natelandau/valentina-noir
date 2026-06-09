"""User avatar controller."""

from typing import Annotated

from litestar import Request
from litestar.controller import Controller
from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.handlers import delete, put
from litestar.params import Body

from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain import deps, hooks, urls
from vapi.domain.services import AvatarService
from vapi.lib.guards import (
    developer_company_user_guard,
    user_active_guard,
    user_self_or_admin_guard,
)
from vapi.lib.rate_limit_policies import ASSET_UPLOAD_LIMIT
from vapi.openapi.tags import APITags

from . import avatar_docs
from .dto import UserResponse
from .helpers import annotated_user_response as _annotated_user_response


class UserAvatarController(Controller):
    """Manage a user's custom avatar."""

    tags = [APITags.USERS.name]
    guards = [developer_company_user_guard, user_active_guard, user_self_or_admin_guard]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "target_user": Provide(deps.provide_target_user),
        "acting_user": Provide(deps.provide_acting_user),
    }

    @put(
        path=urls.Users.AVATAR,
        summary="Set user avatar",
        operation_id="setUserAvatar",
        description=avatar_docs.SET_AVATAR_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
        opt={"rate_limits": [ASSET_UPLOAD_LIMIT]},
    )
    async def set_user_avatar(
        self,
        request: Request,
        company: Company,
        target_user: User,
        acting_user: User,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
    ) -> UserResponse:
        """Upload and set a custom avatar for the user."""
        raw = await data.read()
        await AvatarService().set_avatar(
            user=target_user,
            company_id=company.id,
            acting_user_id=acting_user.id,
            data=raw,
        )
        request.state.audit_description = f"Set avatar for user '{target_user.username}'"
        return await _annotated_user_response(target_user.id)

    @delete(
        path=urls.Users.AVATAR,
        summary="Remove user avatar",
        operation_id="deleteUserAvatar",
        description=avatar_docs.DELETE_AVATAR_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
        status_code=200,
    )
    async def delete_user_avatar(
        self,
        request: Request,
        target_user: User,
        acting_user: User,  # noqa: ARG002  (required for On-Behalf-Of OpenAPI visibility)
    ) -> UserResponse:
        """Remove the user's custom avatar."""
        await AvatarService().remove_avatar(user=target_user)
        request.state.audit_description = f"Remove avatar for user '{target_user.username}'"
        return await _annotated_user_response(target_user.id)
