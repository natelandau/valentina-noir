"""Developer controllers."""

from litestar import Request
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get, patch, post

from vapi.constants import SENSITIVE_RESPONSE_OPT_KEY
from vapi.db.sql_models.developer import Developer
from vapi.domain import deps, hooks, urls
from vapi.domain.services import DeveloperService
from vapi.lib.crypt import hmac_sha256_hex
from vapi.lib.rate_limit_policies import DEVELOPER_KEY_ROTATION_LIMIT
from vapi.lib.stores import delete_authentication_cache_for_developer
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
        opt={"rate_limits": [DEVELOPER_KEY_ROTATION_LIMIT], SENSITIVE_RESPONSE_OPT_KEY: True},
    )
    async def new_api_key(self, *, developer: Developer, request: Request) -> dict[str, str]:
        """Generate a new API key for a developer."""
        # Use the presented key, not the loaded row's, so a rotation that lands between
        # authentication and loading the developer is refused. Evict after the new key is
        # saved: evicting first lets a concurrent request re-cache the old key for the full TTL
        old_fingerprint = hmac_sha256_hex(data=request.auth)
        new_key = await DeveloperService().generate_api_key(
            developer, expected_fingerprint=old_fingerprint
        )
        await delete_authentication_cache_for_developer(
            request.app, developer, fingerprint=old_fingerprint
        )

        request.state.audit_description = f"Regenerate API key for developer '{developer.username}'"
        if developer.key_generated is None:
            msg = f"key_generated not set after generating API key for developer {developer.id}"
            raise ValueError(msg)
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
        changes = await DeveloperService().update(
            developer, data, expected_fingerprint=hmac_sha256_hex(data=request.auth)
        )
        request.state.audit_changes = changes
        request.state.audit_description = f"Update developer '{developer.username}'"
        return DeveloperResponse.from_model(developer)
