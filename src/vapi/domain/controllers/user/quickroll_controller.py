"""Quick roll controller."""

from typing import Annotated

import msgspec
from litestar import Request
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import User
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import UserQuickRollService
from vapi.lib.audit_changes import build_audit_changes
from vapi.lib.guards import developer_company_user_guard, user_active_guard
from vapi.openapi.tags import APITags

from . import docs, dto


class QuickRollController(Controller):
    """User quick roll controller."""

    tags = [APITags.USERS_QUICKROLLS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "quickroll": Provide(deps.provide_quickroll_by_id),
    }
    guards = [developer_company_user_guard, user_active_guard]

    @get(
        path=urls.Users.QUICKROLLS,
        summary="List quick rolls",
        operation_id="listUserQuickrolls",
        description=docs.LIST_QUICKROLLS_DESCRIPTION,
        cache=True,
    )
    async def list_user_quickrolls(
        self,
        user: User,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[dto.QuickRollResponse]:
        """List all user quick rolls."""
        qs = QuickRoll.filter(user=user, is_archived=False).order_by("name")
        count = await qs.count()
        quickrolls = await qs.offset(offset).limit(limit).prefetch_related("traits")
        return OffsetPagination(
            items=[dto.QuickRollResponse.from_model(qr) for qr in quickrolls],
            limit=limit,
            offset=offset,
            total=count,
        )

    @get(
        path=urls.Users.QUICKROLL_DETAIL,
        summary="Get quick roll",
        operation_id="getUserQuickroll",
        description=docs.GET_QUICKROLL_DESCRIPTION,
        cache=True,
    )
    async def get_user_quickroll(self, *, quickroll: QuickRoll) -> dto.QuickRollResponse:
        """Get a user quick roll by ID."""
        return dto.QuickRollResponse.from_model(quickroll)

    @post(
        path=urls.Users.QUICKROLL_CREATE,
        summary="Create quick roll",
        operation_id="createUserQuickroll",
        description=docs.CREATE_QUICKROLL_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def create_user_quickroll(
        self, *, user: User, data: dto.QuickRollCreate
    ) -> dto.QuickRollResponse:
        """Create a user quick roll."""
        service = UserQuickRollService()
        traits = await service.validate_quickroll_traits(data.trait_ids)

        quickroll = await QuickRoll.create(
            user=user,
            name=data.name,
            description=data.description,
        )
        await quickroll.traits.add(*traits)
        # Re-fetch to populate M2M relation after add
        quickroll = await QuickRoll.get(id=quickroll.id).prefetch_related("traits")
        return dto.QuickRollResponse.from_model(quickroll)

    @patch(
        path=urls.Users.QUICKROLL_UPDATE,
        summary="Update quick roll",
        operation_id="updateUserQuickroll",
        description=docs.UPDATE_QUICKROLL_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def update_user_quickroll(
        self, *, quickroll: QuickRoll, data: dto.QuickRollPatch, request: Request
    ) -> dto.QuickRollResponse:
        """Update a user quick roll by ID."""
        changes = build_audit_changes(quickroll, data, exclude=frozenset({"trait_ids"}))
        await quickroll.save()

        if not isinstance(data.trait_ids, msgspec.UnsetType):
            old_trait_ids = sorted(str(t.id) for t in await quickroll.traits.all())
            service = UserQuickRollService()
            traits = await service.validate_quickroll_traits(data.trait_ids)
            await quickroll.traits.clear()
            await quickroll.traits.add(*traits)
            new_trait_ids = sorted(str(tid) for tid in data.trait_ids)
            if old_trait_ids != new_trait_ids:
                changes["trait_ids"] = {"old": old_trait_ids, "new": new_trait_ids}

        request.state.audit_changes = changes

        # Re-fetch to populate M2M relation after potential changes
        quickroll = await QuickRoll.get(id=quickroll.id).prefetch_related("traits")
        return dto.QuickRollResponse.from_model(quickroll)

    @delete(
        path=urls.Users.QUICKROLL_DELETE,
        summary="Delete quick roll",
        operation_id="deleteUserQuickroll",
        description=docs.DELETE_QUICKROLL_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def delete_user_quickroll(self, *, quickroll: QuickRoll) -> None:
        """Delete a user quick roll by ID."""
        quickroll.is_archived = True
        await quickroll.save()
