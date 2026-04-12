"""Developer controllers."""

from litestar import Request
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get, patch, post

from vapi.db.sql_models.developer import Developer
from vapi.domain import deps, hooks, urls
from vapi.domain.services import DeveloperService
from vapi.lib.audit_changes import build_audit_changes
from vapi.lib.rate_limit_policies import DEVELOPER_KEY_ROTATION_LIMIT
from vapi.lib.stores import delete_authentication_cache_for_api_key
from vapi.openapi.tags import APITags

from . import docs
from .dto import DeveloperPatch, DeveloperResponse


class DeveloperController(Controller):
    """Developer controller."""

    tags = [APITags.DEVELOPERS.name]
    dependencies = {
        "developer": Provide(deps.provide_developer_from_request),
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
        opt={"rate_limits": [DEVELOPER_KEY_ROTATION_LIMIT]},
    )
    async def new_api_key(self, *, developer: Developer, request: Request) -> dict[str, str]:
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
        self, *, developer: Developer, data: DeveloperPatch, request: Request
    ) -> DeveloperResponse:
        """Update the current developer."""
        changes = build_audit_changes(developer, data)
        request.state.audit_changes = changes
        await developer.save()

        developer = (
            await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()
        )
        return DeveloperResponse.from_model(developer)
