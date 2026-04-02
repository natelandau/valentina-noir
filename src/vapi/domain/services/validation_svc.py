"""Validation service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from beanie import Document

from vapi.db.models import (
    Campaign,
    Character,
    CharacterConcept,
    CharacterTrait,
    CharSheetSection,
    Developer,
    QuickRoll,
    Trait,
    TraitCategory,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)
from vapi.db.models.base import BaseDocument
from vapi.db.sql_models.character import Character as PgCharacter
from vapi.db.sql_models.character_classes import (
    VampireClan as PgVampireClan,
)
from vapi.db.sql_models.character_classes import (
    WerewolfAuspice as PgWerewolfAuspice,
)
from vapi.db.sql_models.character_classes import (
    WerewolfTribe as PgWerewolfTribe,
)
from vapi.db.sql_models.character_concept import CharacterConcept as PgCharacterConcept
from vapi.db.sql_models.quickroll import QuickRoll as PgQuickRoll
from vapi.db.sql_models.user import User as PgUser
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from uuid import UUID

    from beanie import PydanticObjectId


async def _get_or_raise[T: Document](
    model: type[T],
    doc_id: PydanticObjectId,
    label: str,
    *,
    fetch_links: bool = False,
) -> T:
    """Look up a document by ID and raise ValidationError if not found.

    Automatically filters by is_archived == False for BaseDocument subclasses.

    Args:
        model: The Beanie Document class to query.
        doc_id: The document ID to look up.
        label: Human-readable label for error messages (e.g. "Campaign").
        fetch_links: Whether to fetch linked documents.

    Returns:
        The found document.

    Raises:
        ValidationError: If no matching document exists.
    """
    filters: list = [model.id == doc_id]

    if issubclass(model, BaseDocument):
        filters.append(model.is_archived == False)

    result = await model.find_one(*filters, fetch_links=fetch_links)
    if not result:
        raise ValidationError(detail=f"{label} {doc_id} not found")

    return result


async def _pg_get_or_raise(
    model: Any,
    doc_id: UUID,
    label: str,
) -> Any:
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

    async def get_campaign_by_id(self, campaign_id: PydanticObjectId) -> Campaign:
        """Get a campaign by ID."""
        return await _get_or_raise(Campaign, campaign_id, "Campaign")

    async def get_character_by_id(self, character_id: PydanticObjectId | Any) -> Any:
        """Get a character by ID, routing to Tortoise or Beanie based on ID format.

        During the migration period, unmigrated domains (e.g., character_trait) may pass
        a PydanticObjectId. UUID-format IDs go to Tortoise; ObjectId-format IDs fall
        back to Beanie. This bridge is removed when all callers are migrated.
        """
        import uuid as _uuid_mod

        if isinstance(character_id, _uuid_mod.UUID):
            return await _pg_get_or_raise(PgCharacter, character_id, "Character")

        try:
            uuid_id = _uuid_mod.UUID(str(character_id))
            return await _pg_get_or_raise(PgCharacter, uuid_id, "Character")
        except ValueError:
            pass

        return await _get_or_raise(Character, character_id, "Character")

    async def get_concept_by_id(self, concept_id: PydanticObjectId) -> CharacterConcept:
        """Get a concept by ID."""
        return await _get_or_raise(CharacterConcept, concept_id, "Concept")

    async def get_vampire_clan_by_id(self, vampire_clan_id: PydanticObjectId) -> VampireClan:
        """Get a vampire clan by ID."""
        return await _get_or_raise(VampireClan, vampire_clan_id, "Vampire clan")

    async def get_werewolf_auspice_by_id(
        self, werewolf_auspice_id: PydanticObjectId
    ) -> WerewolfAuspice:
        """Get a werewolf auspice by ID."""
        return await _get_or_raise(WerewolfAuspice, werewolf_auspice_id, "Werewolf auspice")

    async def get_werewolf_tribe_by_id(self, werewolf_tribe_id: PydanticObjectId) -> WerewolfTribe:
        """Get a werewolf tribe by ID."""
        return await _get_or_raise(WerewolfTribe, werewolf_tribe_id, "Werewolf tribe")

    async def get_concept_by_uuid(self, concept_id: UUID) -> Any:
        """Get a concept by UUID via Tortoise."""
        return await _pg_get_or_raise(PgCharacterConcept, concept_id, "Concept")

    async def get_vampire_clan_by_uuid(self, vampire_clan_id: UUID) -> Any:
        """Get a vampire clan by UUID via Tortoise."""
        return await _pg_get_or_raise(PgVampireClan, vampire_clan_id, "Vampire clan")

    async def get_werewolf_auspice_by_uuid(self, werewolf_auspice_id: UUID) -> Any:
        """Get a werewolf auspice by UUID via Tortoise."""
        return await _pg_get_or_raise(PgWerewolfAuspice, werewolf_auspice_id, "Werewolf auspice")

    async def get_werewolf_tribe_by_uuid(self, werewolf_tribe_id: UUID) -> Any:
        """Get a werewolf tribe by UUID via Tortoise."""
        return await _pg_get_or_raise(PgWerewolfTribe, werewolf_tribe_id, "Werewolf tribe")

    async def get_developer_by_id(self, developer_id: PydanticObjectId) -> Developer:
        """Get a developer by ID."""
        return await _get_or_raise(Developer, developer_id, "Developer")

    async def get_quickroll_by_id(self, quickroll_id: PydanticObjectId) -> QuickRoll:
        """Get a quick roll by ID."""
        return await _get_or_raise(QuickRoll, quickroll_id, "Quick roll")

    async def get_quickroll_by_uuid(self, quickroll_id: UUID) -> Any:
        """Get a quick roll by UUID via Tortoise."""
        return await _pg_get_or_raise(PgQuickRoll, quickroll_id, "Quick roll")

    async def get_user_by_id(self, user_id: UUID | Any) -> Any:
        """Get a user by ID, routing to Tortoise or Beanie based on ID format.

        During the migration period, unmigrated domains (e.g., character_trait) may pass
        a PydanticObjectId. UUID-format IDs go to Tortoise; ObjectId-format IDs fall
        back to Beanie. This bridge is removed when all callers are migrated.
        """
        import uuid as _uuid_mod

        # UUID-format IDs go to Tortoise (the migrated User table)
        if isinstance(user_id, _uuid_mod.UUID):
            return await _pg_get_or_raise(PgUser, user_id, "User")

        # Try parsing as UUID — if it works, use Tortoise
        try:
            uuid_id = _uuid_mod.UUID(str(user_id))
            return await _pg_get_or_raise(PgUser, uuid_id, "User")
        except ValueError:
            pass

        # ObjectId-format IDs fall back to Beanie for unmigrated callers
        from vapi.db.models import User as BeanieUser

        return await _get_or_raise(BeanieUser, user_id, "User")

    async def get_character_trait_by_id(
        self, character_trait_id: PydanticObjectId, *, fetch_links: bool = True
    ) -> CharacterTrait:
        """Get a character trait by ID.

        Args:
            character_trait_id: The ID of the character trait to get.
            fetch_links: Whether to fetch the links for the character trait.

        Returns:
            The character trait.

        Raises:
            ValidationError: If the character trait is not found.
        """
        return await _get_or_raise(
            CharacterTrait, character_trait_id, "Character trait", fetch_links=fetch_links
        )

    async def get_trait_by_id(self, trait_id: PydanticObjectId) -> Trait:
        """Get a trait by ID."""
        return await _get_or_raise(Trait, trait_id, "Trait")

    async def get_trait_category_by_id(self, trait_category_id: PydanticObjectId) -> TraitCategory:
        """Get a trait category by ID."""
        return await _get_or_raise(TraitCategory, trait_category_id, "Trait category")

    async def get_sheet_section_by_id(self, sheet_section_id: PydanticObjectId) -> CharSheetSection:
        """Get a sheet section by ID."""
        return await _get_or_raise(CharSheetSection, sheet_section_id, "Sheet section")
