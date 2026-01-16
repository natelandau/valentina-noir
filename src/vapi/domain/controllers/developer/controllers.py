"""Developer controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from litestar.controller import Controller
from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import get, patch, post
from pydantic import ValidationError as PydanticValidationError

from vapi.db.models import Developer  # noqa: TC001
from vapi.domain import deps, hooks, urls
from vapi.domain.utils import patch_dto_data_internal_objects
from vapi.lib.stores import delete_authentication_cache_for_api_key
from vapi.openapi.tags import APITags
from vapi.utils.validation import raise_from_pydantic_validation_error

from . import dto

if TYPE_CHECKING:
    from litestar import Request


class DeveloperController(Controller):
    """Developer controller."""

    tags = [APITags.DEVELOPERS.name]
    dependencies = {
        "developer": Provide(deps.provide_developer_from_request),
    }
    return_dto = dto.ReturnDTO

    @get(
        path=urls.Developers.ME,
        summary="Get current developer",
        operation_id="getDeveloperMe",
        description="Retrieve the developer profile associated with the current API key. Use this to verify authentication and view your account details.",
        cache=True,
    )
    async def me(self, *, developer: Developer) -> Developer:
        """Get the current developer."""
        return developer

    @post(
        path=urls.Developers.NEW_KEY,
        summary="Regenerate API key",
        operation_id="regenerateDeveloperMeApiKey",
        description="Generate a new API key for your account. The current key will be immediately invalidated and all cached authentication data will be cleared.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def new_api_key(self, *, developer: Developer, request: Request) -> dict[str, str]:
        """Generate a new API key for an Developer."""
        new_api_key = await developer.generate_api_key()

        await delete_authentication_cache_for_api_key(request)
        return {
            "id": str(developer.id),
            "username": developer.username,
            "email": developer.email,
            "api_key": new_api_key,
            "key_generated": developer.key_generated.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    @patch(
        path=urls.Developers.UPDATE,
        summary="Update current developer",
        operation_id="updateDeveloperMe",
        description="Modify your developer profile. Only include fields that need to be changed; omitted fields remain unchanged.",
        dto=dto.PatchDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def update_developer(
        self, *, developer: Developer, data: DTOData[Developer]
    ) -> Developer:
        """Update the current developer."""
        developer, data = await patch_dto_data_internal_objects(original=developer, data=data)
        updated_developer = data.update_instance(developer)
        try:
            await updated_developer.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return updated_developer
