"""Character Generation API."""

import logging
from datetime import timedelta
from uuid import UUID

from litestar import Request
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get, post

from vapi.constants import CharacterType
from vapi.db.sql_models import (
    Campaign,
    Character,
    ChargenSession,
    Company,
    User,
)
from vapi.domain import hooks, urls
from vapi.domain.controllers.character.dto import CHARACTER_RESPONSE_PREFETCH, CharacterResponse
from vapi.domain.deps import (
    provide_acting_user,
    provide_campaign_by_id,
    provide_character_by_id_and_company,
    provide_company_by_id,
)
from vapi.domain.handlers.character_autogeneration.handler import CharacterAutogenerationHandler
from vapi.domain.services import CharacterService, GetModelByIdValidationService
from vapi.domain.services.user_svc import UserXPService
from vapi.lib.exceptions import ValidationError
from vapi.lib.guards import (
    developer_company_user_guard,
    user_active_guard,
    user_storyteller_guard,
)
from vapi.openapi.tags import APITags
from vapi.utils.time import time_now

from .docs import (
    AUTOGEN_DOCUMENTATION,
    CHARGEN_FINALIZE_DOCUMENTATION,
    CHARGEN_SESSION_DETAIL_DOCUMENTATION,
    CHARGEN_SESSIONS_LIST_DOCUMENTATION,
    CHARGEN_START_DOCUMENTATION,
)
from .dto import ChargenSessionFinalizeRequest, ChargenSessionResponse, CreateAutogenerateRequest

logger = logging.getLogger("vapi")

CHARGEN_SESSION_PREFETCH: list[str] = [
    "characters",
    *[f"characters__{p}" for p in CHARACTER_RESPONSE_PREFETCH],
]


class CharacterGenerationController(Controller):
    """Character autogeneration controller."""

    tags = [APITags.CHARACTERS_AUTOGEN.name]
    dependencies = {
        "company": Provide(provide_company_by_id),
        "acting_user": Provide(provide_acting_user),
        "campaign": Provide(provide_campaign_by_id),
        "character": Provide(provide_character_by_id_and_company),
    }
    guards = [developer_company_user_guard, user_active_guard]

    @post(
        path=urls.Characters.AUTOGENERATE,
        summary="Autogenerate character",
        operation_id="autogenerateCharacter",
        description=AUTOGEN_DOCUMENTATION,
        guards=[user_storyteller_guard],
        after_response=hooks.post_data_update_hook,
    )
    async def autogenerate_character_all_random(
        self,
        company: Company,
        acting_user: User,
        campaign: Campaign,
        data: CreateAutogenerateRequest,
        request: Request,
    ) -> CharacterResponse:
        """Create a new character."""
        validation_service = GetModelByIdValidationService()
        concept = (
            await validation_service.get_concept_by_id(data.concept_id) if data.concept_id else None
        )
        vampire_clan = (
            await validation_service.get_vampire_clan_by_id(data.vampire_clan_id)
            if data.vampire_clan_id
            else None
        )
        werewolf_tribe = (
            await validation_service.get_werewolf_tribe_by_id(data.werewolf_tribe_id)
            if data.werewolf_tribe_id
            else None
        )
        werewolf_auspice = (
            await validation_service.get_werewolf_auspice_by_id(data.werewolf_auspice_id)
            if data.werewolf_auspice_id
            else None
        )

        chargen = CharacterAutogenerationHandler(
            company=company,
            user=acting_user,
            campaign=campaign,
        )
        new_character = await chargen.generate_character(
            character_type=data.character_type,
            experience_level=data.experience_level,
            skill_focus=data.skill_focus,
            char_class=data.character_class,
            concept=concept,
            vampire_clan=vampire_clan,
            werewolf_tribe=werewolf_tribe,
            werewolf_auspice=werewolf_auspice,
        )

        service = CharacterService()
        await service.prepare_for_save(new_character)
        await new_character.save()

        # Re-fetch with prefetch for DTO conversion
        new_character = (
            await Character.filter(id=new_character.id)
            .prefetch_related(*CHARACTER_RESPONSE_PREFETCH)
            .first()
        )
        request.state.audit_description = f"Autogenerate {new_character.type.value.lower()} character '{new_character.name_first} {new_character.name_last} ({new_character.character_class.value.lower()})'"

        return CharacterResponse.from_model(new_character)

    @post(
        path=urls.Characters.CHARGEN_START,
        summary="Start player character generation",
        operation_id="startChargenSession",
        description=CHARGEN_START_DOCUMENTATION,
        after_response=hooks.post_data_update_hook,
    )
    async def start_chargen(
        self,
        company: Company,
        acting_user: User,
        campaign: Campaign,
    ) -> ChargenSessionResponse:
        """Generate multiple character options."""
        settings = company.settings
        num_choices = settings.character_autogen_num_choices or 1

        xp_cost = settings.character_autogen_xp_cost or 0
        if xp_cost > 0:
            await UserXPService().spend_xp(acting_user.id, campaign.id, xp_cost)

        chargen = CharacterAutogenerationHandler(
            company=company, user=acting_user, campaign=campaign
        )
        service = CharacterService()
        characters: list[Character] = []
        for _ in range(num_choices):
            character = await chargen.generate_character(
                character_type=CharacterType.PLAYER,
            )
            character.is_chargen = True
            character.is_temporary = num_choices > 1
            await service.prepare_for_save(character)
            await character.save()
            characters.append(character)

        session = await ChargenSession.create(
            user=acting_user,
            company=company,
            campaign=campaign,
            expires_at=time_now() + timedelta(hours=24),
            requires_selection=num_choices > 1,
        )
        await session.characters.add(*characters)

        # Re-fetch with prefetch for DTO conversion
        session = (
            await ChargenSession.filter(id=session.id)
            .prefetch_related(*CHARGEN_SESSION_PREFETCH)
            .first()
        )

        return ChargenSessionResponse.from_model(session)

    @post(
        path=urls.Characters.CHARGEN_FINALIZE,
        summary="Finalize character selection",
        operation_id="finalizeChargenSession",
        description=CHARGEN_FINALIZE_DOCUMENTATION,
        after_response=hooks.post_data_update_hook,
    )
    async def finalize_chargen(
        self,
        company: Company,
        data: ChargenSessionFinalizeRequest,
        request: Request,
    ) -> CharacterResponse:
        """Finalize character selection from a chargen session and cleanup unselected options."""
        session = (
            await ChargenSession.filter(id=data.session_id, company=company)
            .prefetch_related(*CHARGEN_SESSION_PREFETCH)
            .first()
        )

        if not session:
            raise ValidationError(
                invalid_parameters=[{"field": "session_id", "message": "Session not found"}]
            )

        selected_character = next(
            (c for c in session.characters if c.id == data.selected_character_id),
            None,
        )
        if not selected_character:
            raise ValidationError(
                invalid_parameters=[
                    {"field": "selected_character_id", "message": "Character not in session"}
                ]
            )

        # Promote selected character
        selected_character.is_temporary = False
        selected_character.is_chargen = False
        service = CharacterService()
        await service.prepare_for_save(selected_character)
        await selected_character.save()

        # Delete unselected characters
        for char in session.characters:
            if char.id != selected_character.id:
                await char.delete()

        # Delete the session
        await session.delete()

        # Re-fetch with prefetch for DTO conversion
        selected_character = (
            await Character.filter(id=selected_character.id)
            .prefetch_related(*CHARACTER_RESPONSE_PREFETCH)
            .first()
        )

        request.state.audit_description = f"Finalize chargen session {session.id} and promote character '{selected_character.name_first} {selected_character.name_last} ({selected_character.character_class.value.lower()})'"

        return CharacterResponse.from_model(selected_character)

    @get(
        path=urls.Characters.CHARGEN_SESSIONS,
        summary="List active chargen sessions",
        operation_id="listChargenSessions",
        description=CHARGEN_SESSIONS_LIST_DOCUMENTATION,
    )
    async def list_chargen_sessions(
        self,
        company: Company,
        acting_user: User,
    ) -> list[ChargenSessionResponse]:
        """List all active chargen sessions for this user."""
        sessions = await ChargenSession.filter(
            company=company,
            user=acting_user,
            expires_at__gt=time_now(),
        ).prefetch_related(*CHARGEN_SESSION_PREFETCH)

        return [ChargenSessionResponse.from_model(s) for s in sessions]

    @get(
        path=urls.Characters.CHARGEN_SESSION_DETAIL,
        summary="Get chargen session by ID",
        operation_id="getChargenSession",
        description=CHARGEN_SESSION_DETAIL_DOCUMENTATION,
    )
    async def get_chargen_session(
        self,
        company: Company,
        session_id: UUID,
    ) -> ChargenSessionResponse:
        """Retrieve a specific chargen session by its ID."""
        session = (
            await ChargenSession.filter(
                id=session_id,
                company=company,
                expires_at__gt=time_now(),
            )
            .prefetch_related(*CHARGEN_SESSION_PREFETCH)
            .first()
        )

        if not session:
            raise ValidationError(
                invalid_parameters=[
                    {"field": "session_id", "message": "Session not found or expired"}
                ]
            )

        return ChargenSessionResponse.from_model(session)
