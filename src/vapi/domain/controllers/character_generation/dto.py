"""Character generation DTOs."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import msgspec

from vapi.constants import CharacterClass, CharacterType
from vapi.domain.controllers.character.dto import CharacterResponse
from vapi.domain.handlers.character_autogeneration.constants import (
    AbilityFocus,
    AutoGenExperienceLevel,
)

if TYPE_CHECKING:
    from vapi.db.sql_models.chargen_session import ChargenSession


class CreateAutogenerateRequest(msgspec.Struct):
    """Request body for autogenerating a character."""

    character_type: CharacterType
    character_class: CharacterClass | None = None
    experience_level: AutoGenExperienceLevel | None = None
    skill_focus: AbilityFocus | None = None
    concept_id: UUID | None = None
    vampire_clan_id: UUID | None = None
    werewolf_tribe_id: UUID | None = None
    werewolf_auspice_id: UUID | None = None


class ChargenSessionFinalizeRequest(msgspec.Struct):
    """Request body for finalizing a chargen session."""

    session_id: UUID
    selected_character_id: UUID


class ChargenSessionResponse(msgspec.Struct):
    """Response body for a chargen session."""

    id: UUID
    user_id: UUID
    campaign_id: UUID
    expires_at: datetime
    requires_selection: bool
    characters: list[CharacterResponse]
    date_created: datetime
    date_modified: datetime

    @classmethod
    def from_model(cls, session: "ChargenSession") -> "ChargenSessionResponse":
        """Convert a Tortoise ChargenSession to a response Struct.

        Requires prefetch_related('characters', and all CHARACTER_RESPONSE_PREFETCH
        nested under characters).
        """
        characters = [CharacterResponse.from_model(c) for c in session.characters]
        return cls(
            id=session.id,
            user_id=session.user_id,  # type: ignore[attr-defined]
            campaign_id=session.campaign_id,  # type: ignore[attr-defined]
            expires_at=session.expires_at,
            requires_selection=session.requires_selection,
            characters=characters,
            date_created=session.date_created,
            date_modified=session.date_modified,
        )
