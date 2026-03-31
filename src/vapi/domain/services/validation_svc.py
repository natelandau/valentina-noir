"""Validation service."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    User,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)
from vapi.db.models.base import BaseDocument
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
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


class GetModelByIdValidationService:
    """Get model by ID validation service."""

    async def get_campaign_by_id(self, campaign_id: PydanticObjectId) -> Campaign:
        """Get a campaign by ID."""
        return await _get_or_raise(Campaign, campaign_id, "Campaign")

    async def get_character_by_id(self, character_id: PydanticObjectId) -> Character:
        """Get a character by ID."""
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

    async def get_developer_by_id(self, developer_id: PydanticObjectId) -> Developer:
        """Get a developer by ID."""
        return await _get_or_raise(Developer, developer_id, "Developer")

    async def get_quickroll_by_id(self, quickroll_id: PydanticObjectId) -> QuickRoll:
        """Get a quick roll by ID."""
        return await _get_or_raise(QuickRoll, quickroll_id, "Quick roll")

    async def get_user_by_id(self, user_id: PydanticObjectId) -> User:
        """Get a user by ID."""
        return await _get_or_raise(User, user_id, "User")

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
