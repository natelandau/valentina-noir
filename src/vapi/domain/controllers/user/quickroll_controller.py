"""Quick roll controller."""

from __future__ import annotations

from typing import Annotated

from litestar.controller import Controller
from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter
from pydantic import ValidationError as PydanticValidationError

from vapi.db.models import QuickRoll, User
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import UserQuickRollService
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags
from vapi.utils.validation import raise_from_pydantic_validation_error

from . import dto


class QuickRollController(Controller):
    """User quick roll controller."""

    tags = [APITags.USERS_QUICKROLLS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "quickroll": Provide(deps.provide_quickroll_by_id),
    }
    guards = [developer_company_user_guard]
    return_dto = dto.ReturnQuickRollDTO

    @get(
        path=urls.Users.QUICKROLLS,
        summary="List quick rolls",
        operation_id="listUserQuickrolls",
        description="Retrieve a paginated list of quick rolls saved by a user. Quick rolls are pre-configured dice pools for frequently used trait combinations.",
        cache=True,
        return_dto=dto.ReturnQuickRollDTO,
    )
    async def list_user_quickrolls(
        self,
        user: User,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[QuickRoll]:
        """List all user quick rolls."""
        query = {"user_id": user.id, "is_archived": False}
        count = await QuickRoll.find(query).count()
        quickrolls = await QuickRoll.find(query).sort("name").skip(offset).limit(limit).to_list()

        return OffsetPagination(items=quickrolls, limit=limit, offset=offset, total=count)

    @get(
        path=urls.Users.QUICKROLL_DETAIL,
        summary="Get quick roll",
        operation_id="getUserQuickroll",
        description="Retrieve details of a specific quick roll including its associated traits.",
        cache=True,
        return_dto=dto.ReturnQuickRollDTO,
    )
    async def get_user_quickroll(self, *, quickroll: QuickRoll) -> QuickRoll:
        """Get a user quick roll by ID."""
        return quickroll

    @post(
        path=urls.Users.QUICKROLL_CREATE,
        summary="Create quick roll",
        operation_id="createUserQuickroll",
        description="Create a new quick roll for a user. Define the traits that make up the dice pool. Quick roll names must be unique per user.",
        dto=dto.PostQuickRollDTO,
        return_dto=dto.ReturnQuickRollDTO,
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def create_user_quickroll(self, *, user: User, data: DTOData[QuickRoll]) -> QuickRoll:
        """Create a user quick roll."""
        try:
            quickroll_data = data.create_instance(user_id=user.id)
            quickroll = QuickRoll(**quickroll_data.model_dump(exclude_unset=True))
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        service = UserQuickRollService()
        validated_quickroll = await service.validate_quickroll(quickroll)
        await validated_quickroll.save()

        return validated_quickroll

    @patch(
        path=urls.Users.QUICKROLL_UPDATE,
        summary="Update quick roll",
        operation_id="updateUserQuickroll",
        description="Modify a quick roll's name or trait configuration. Only include fields that need to be changed.",
        dto=dto.PatchQuickRollDTO,
        return_dto=dto.ReturnQuickRollDTO,
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def update_user_quickroll(
        self, *, quickroll: QuickRoll, data: DTOData[QuickRoll]
    ) -> QuickRoll:
        """Update a user quick roll by ID."""
        updated_quickroll = data.update_instance(quickroll)

        service = UserQuickRollService()
        validated_quickroll = await service.validate_quickroll(updated_quickroll)

        try:
            await validated_quickroll.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return validated_quickroll

    @delete(
        path=urls.Users.QUICKROLL_DELETE,
        summary="Delete quick roll",
        operation_id="deleteUserQuickroll",
        description="Remove a quick roll from a user. This action cannot be undone.",
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def delete_user_quickroll(self, *, quickroll: QuickRoll) -> None:
        """Delete a user quick roll by ID."""
        quickroll.is_archived = True
        await quickroll.save()
