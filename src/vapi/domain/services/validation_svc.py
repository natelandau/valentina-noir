"""Validation service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise.expressions import Q
from tortoise.models import Model

from vapi.db.sql_models.campaign import Campaign
from vapi.db.sql_models.character import Character, CharacterTrait
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept, concept_visible_to_company_q
from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import User
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from uuid import UUID


async def _get_or_raise[M: Model](
    model: type[M],
    doc_id: UUID,
    label: str,
    *filters: Q,
) -> M:
    """Look up a Tortoise record by ID and raise ValidationError if not found.

    Args:
        model: The Tortoise Model class to query.
        doc_id: The record UUID to look up.
        label: Human-readable label for error messages.
        *filters: Extra conditions, such as a company scope, the record must match.

    Raises:
        ValidationError: If no matching record exists.
    """
    result = await model.filter(*filters, id=doc_id, is_archived=False).first()
    if not result:
        raise ValidationError(detail=f"{label} {doc_id} not found")

    return result


async def validate_trait_ids_from_mixed_sources(
    trait_ids: list[UUID],
    *,
    company_id: UUID,
) -> list[UUID]:
    """Validate a list of trait IDs or character trait IDs and return valid trait IDs.

    Accept a mixed list of trait UUIDs and character trait UUIDs,
    validate each one, and return a list of the corresponding trait UUIDs.
    Uses two batch queries instead of per-ID lookups.

    Args:
        trait_ids: The list of trait or character trait UUIDs to validate.
        company_id: The company whose custom traits and character traits may be used.

    Returns:
        The list of validated trait UUIDs.

    Raises:
        ValidationError: If any of the trait IDs are invalid.
    """
    if not trait_ids:
        return []

    unique_ids = set(trait_ids)

    # Batch 1: check which IDs are direct Trait IDs
    matching_traits = await Trait.filter(
        Q(custom_for_character_id__isnull=True) | Q(custom_for_character__company_id=company_id),
        id__in=unique_ids,
    )
    resolved: dict[UUID, UUID] = {t.id: t.id for t in matching_traits}

    # Batch 2: resolve remaining IDs as CharacterTrait IDs
    remaining_ids = unique_ids - resolved.keys()
    if remaining_ids:
        character_traits = await CharacterTrait.filter(
            id__in=remaining_ids, character__company_id=company_id
        ).select_related("trait")
        for ct in character_traits:
            resolved[ct.id] = ct.trait.id

    # Check for any unresolved IDs
    unresolved = unique_ids - resolved.keys()
    if unresolved:
        bad_id = next(iter(unresolved))
        raise ValidationError(
            detail="Trait not found",
            invalid_parameters=[
                {"field": "trait_ids", "message": f"Trait {bad_id} not found"},
            ],
        )

    return [resolved[tid] for tid in trait_ids]


class GetModelByIdValidationService:
    """Get model by ID validation service."""

    async def get_campaign_by_id(self, campaign_id: UUID, *, company_id: UUID) -> Campaign:
        """Get a campaign by ID within a company."""
        return await _get_or_raise(Campaign, campaign_id, "Campaign", Q(company_id=company_id))

    async def get_character_by_id(self, character_id: UUID, *, company_id: UUID) -> Character:
        """Get a character by ID within a company."""
        return await _get_or_raise(Character, character_id, "Character", Q(company_id=company_id))

    async def get_concept_by_id(self, concept_id: UUID, *, company_id: UUID) -> CharacterConcept:
        """Get a shared concept or one owned by the company."""
        return await _get_or_raise(
            CharacterConcept, concept_id, "Concept", concept_visible_to_company_q(company_id)
        )

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

    async def get_quickroll_by_id(self, quickroll_id: UUID, *, company_id: UUID) -> QuickRoll:
        """Get a quick roll by ID owned by a user in a company."""
        return await _get_or_raise(
            QuickRoll, quickroll_id, "Quick roll", Q(user__company_id=company_id)
        )
