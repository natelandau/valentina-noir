"""Validation service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise.models import Model

from vapi.db.sql_models.campaign import Campaign
from vapi.db.sql_models.character import Character
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import User
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from uuid import UUID


async def _get_or_raise[M: Model](
    model: type[M],
    doc_id: UUID,
    label: str,
) -> M:
    """Look up a Tortoise record by ID and raise ValidationError if not found.

    Args:
        model: The Tortoise Model class to query.
        doc_id: The record UUID to look up.
        label: Human-readable label for error messages.

    Raises:
        ValidationError: If no matching record exists.
    """
    result = await model.filter(id=doc_id, is_archived=False).first()
    if not result:
        raise ValidationError(detail=f"{label} {doc_id} not found")

    return result


class GetModelByIdValidationService:
    """Get model by ID validation service."""

    async def get_campaign_by_id(self, campaign_id: UUID) -> Campaign:
        """Get a campaign by ID."""
        return await _get_or_raise(Campaign, campaign_id, "Campaign")

    async def get_character_by_id(self, character_id: UUID) -> Character:
        """Get a character by ID."""
        return await _get_or_raise(Character, character_id, "Character")

    async def get_concept_by_id(self, concept_id: UUID) -> CharacterConcept:
        """Get a concept by ID."""
        return await _get_or_raise(CharacterConcept, concept_id, "Concept")

    async def get_vampire_clan_by_id(self, vampire_clan_id: UUID) -> VampireClan:
        """Get a vampire clan by ID."""
        return await _get_or_raise(VampireClan, vampire_clan_id, "Vampire clan")

    async def get_werewolf_auspice_by_id(self, werewolf_auspice_id: UUID) -> WerewolfAuspice:
        """Get a werewolf auspice by ID."""
        return await _get_or_raise(WerewolfAuspice, werewolf_auspice_id, "Werewolf auspice")

    async def get_werewolf_tribe_by_id(self, werewolf_tribe_id: UUID) -> WerewolfTribe:
        """Get a werewolf tribe by ID."""
        return await _get_or_raise(WerewolfTribe, werewolf_tribe_id, "Werewolf tribe")

    async def get_user_by_id(self, user_id: UUID) -> User:
        """Get a user by ID."""
        return await _get_or_raise(User, user_id, "User")

    async def get_quickroll_by_id(self, quickroll_id: UUID) -> QuickRoll:
        """Get a quick roll by ID."""
        return await _get_or_raise(QuickRoll, quickroll_id, "Quick roll")
