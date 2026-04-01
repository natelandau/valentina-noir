"""Developer controllers."""

from typing import TYPE_CHECKING

import msgspec
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get, patch, post

from vapi.db.sql_models.developer import Developer
from vapi.domain import hooks, pg_deps, urls
from vapi.domain.services import DeveloperService
from vapi.lib.stores import delete_authentication_cache_for_api_key
from vapi.openapi.tags import APITags

from . import docs
from .dto import DeveloperPatch, DeveloperResponse

if TYPE_CHECKING:
    from litestar import Request


class DeveloperController(Controller):
    """Developer controller."""

    tags = [APITags.DEVELOPERS.name]
    dependencies = {
        "developer": Provide(pg_deps.provide_developer_from_request),
    }

    @get(
        path=urls.Developers.ME,
        summary="Get current developer",
        operation_id="getDeveloperMe",
        description=docs.GET_ME_DESCRIPTION,
        cache=True,
    )
    async def me(self, *, developer: Developer) -> DeveloperResponse:
        """Get the current developer."""
        return DeveloperResponse.from_model(developer)

    @post(
        path=urls.Developers.NEW_KEY,
        summary="Regenerate API key",
        operation_id="regenerateDeveloperMeApiKey",
        description=docs.REGENERATE_API_KEY_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def new_api_key(self, *, developer: Developer, request: "Request") -> dict[str, str]:
        """Generate a new API key for a developer."""
        new_key = await DeveloperService().generate_api_key(developer)

        await delete_authentication_cache_for_api_key(request)
        return {
            "id": str(developer.id),
            "username": developer.username,
            "email": developer.email,
            "api_key": new_key,
            "key_generated": developer.key_generated.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    @patch(
        path=urls.Developers.UPDATE,
        summary="Update current developer",
        operation_id="updateDeveloperMe",
        description=docs.UPDATE_ME_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def update_developer(
        self, *, developer: Developer, data: DeveloperPatch
    ) -> DeveloperResponse:
        """Update the current developer."""
        if not isinstance(data.username, msgspec.UnsetType):
            developer.username = data.username
        if not isinstance(data.email, msgspec.UnsetType):
            developer.email = data.email

        await developer.save()

        # Re-fetch with prefetched relations so the response DTO has full data
        developer = (
            await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()
        )  # type: ignore[assignment]

        return DeveloperResponse.from_model(developer)
