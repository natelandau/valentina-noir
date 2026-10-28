"""Character health controllers."""

from litestar import Request
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get, post, put

from vapi.constants import AuditOperation
from vapi.db.sql_models.character import Character, CharacterHealth
from vapi.db.sql_models.user import User
from vapi.domain import deps, hooks, urls
from vapi.domain.controllers.character_trait.dto import TrackerActionRequest
from vapi.domain.services import TrackerService
from vapi.lib.exceptions import NotFoundError
from vapi.lib.guards import (
    developer_company_user_guard,
    storyteller_character_access_guard,
    user_active_guard,
    user_character_player_or_storyteller_guard,
)
from vapi.openapi.tags import APITags

from . import docs
from .dto import HealthResponse, HealthStateSet


class CharacterHealthController(Controller):
    """Character health controller."""

    tags = [APITags.CHARACTERS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "acting_user": Provide(deps.provide_acting_user),
        "character": Provide(deps.provide_character_by_id_and_company),
        "developer": Provide(deps.provide_developer_from_request),
    }
    guards = [developer_company_user_guard, user_active_guard, storyteller_character_access_guard]

    @get(
        path=urls.Characters.HEALTH,
        summary="Get character health",
        operation_id="getCharacterHealth",
        description=docs.GET_HEALTH_DESCRIPTION,
        cache=True,
    )
    async def get_character_health(self, character: Character) -> HealthResponse:
        """Get a character's health track."""
        health = await CharacterHealth.get_or_none(character_id=character.id, is_archived=False)
        if health is None:
            raise NotFoundError(detail="Character health not found")
        return HealthResponse.from_model(health, character=character)

    @put(
        path=urls.Characters.HEALTH,
        summary="Set character health",
        operation_id="setCharacterHealth",
        description=docs.SET_HEALTH_DESCRIPTION,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.post_data_update_hook,
        status_code=200,
    )
    async def set_character_health(
        self,
        request: Request,
        character: Character,
        acting_user: User,  # noqa: ARG002
        data: HealthStateSet,
    ) -> HealthResponse:
        """Set a character's full health state."""
        service = TrackerService()
        response = await service.set_health_state(character=character, data=data)
        request.state.audit_description = service.audit_description
        request.state.audit_changes = service.audit_changes
        return response

    @post(
        path=urls.Characters.HEALTH_ACTIONS,
        summary="Apply character health action",
        operation_id="applyCharacterHealthAction",
        description=docs.APPLY_HEALTH_ACTION_DESCRIPTION,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.post_data_update_hook,
        status_code=200,
    )
    async def apply_character_health_action(
        self,
        request: Request,
        character: Character,
        acting_user: User,  # noqa: ARG002
        data: TrackerActionRequest,
    ) -> HealthResponse:
        """Apply one damage, heal, or reset action to a character's health."""
        service = TrackerService()
        response = await service.apply_health_action(character=character, data=data)
        request.state.audit_operation = AuditOperation.UPDATE
        request.state.audit_description = service.audit_description
        request.state.audit_changes = service.audit_changes
        return response
