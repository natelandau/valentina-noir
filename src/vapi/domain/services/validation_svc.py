"""Validation service."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from beanie import PydanticObjectId


class GetModelByIdValidationService:
    """Get model by ID validation service."""

    async def get_campaign_by_id(self, campaign_id: PydanticObjectId) -> Campaign:
        """Get a campaign by ID."""
        campaign = await Campaign.find_one(
            Campaign.id == campaign_id,
            Campaign.is_archived == False,
        )
        if not campaign:
            raise ValidationError(detail=f"Campaign {campaign_id} not found")
        return campaign

    async def get_character_by_id(self, character_id: PydanticObjectId) -> Character:
        """Get a character by ID."""
        character = await Character.find_one(
            Character.id == character_id,
            Character.is_archived == False,
        )
        if not character:
            raise ValidationError(detail=f"Character {character_id} not found")
        return character

    async def get_concept_by_id(self, concept_id: PydanticObjectId) -> CharacterConcept:
        """Get a concept by ID."""
        concept = await CharacterConcept.find_one(
            CharacterConcept.id == concept_id,
            CharacterConcept.is_archived == False,
        )
        if not concept:
            raise ValidationError(detail=f"Concept {concept_id} not found")
        return concept

    async def get_vampire_clan_by_id(self, vampire_clan_id: PydanticObjectId) -> VampireClan:
        """Get a vampire clan by ID."""
        vampire_clan = await VampireClan.find_one(
            VampireClan.id == vampire_clan_id,
            VampireClan.is_archived == False,
        )
        if not vampire_clan:
            raise ValidationError(detail=f"Vampire clan {vampire_clan_id} not found")
        return vampire_clan

    async def get_werewolf_auspice_by_id(
        self, werewolf_auspice_id: PydanticObjectId
    ) -> WerewolfAuspice:
        """Get a werewolf auspice by ID."""
        werewolf_auspice = await WerewolfAuspice.find_one(
            WerewolfAuspice.id == werewolf_auspice_id,
            WerewolfAuspice.is_archived == False,
        )
        if not werewolf_auspice:
            raise ValidationError(detail=f"Werewolf auspice {werewolf_auspice_id} not found")
        return werewolf_auspice

    async def get_werewolf_tribe_by_id(self, werewolf_tribe_id: PydanticObjectId) -> WerewolfTribe:
        """Get a werewolf tribe by ID."""
        werewolf_tribe = await WerewolfTribe.find_one(
            WerewolfTribe.id == werewolf_tribe_id,
            WerewolfTribe.is_archived == False,
        )
        if not werewolf_tribe:
            raise ValidationError(detail=f"Werewolf tribe {werewolf_tribe_id} not found")
        return werewolf_tribe

    async def get_developer_by_id(self, developer_id: PydanticObjectId) -> Developer:
        """Get a developer by ID."""
        developer = await Developer.find_one(
            Developer.id == developer_id,
            Developer.is_archived == False,
        )
        if not developer:
            raise ValidationError(detail=f"Developer {developer_id} not found")
        return developer

    async def get_quickroll_by_id(self, quickroll_id: PydanticObjectId) -> QuickRoll:
        """Get a quick roll by ID."""
        quickroll = await QuickRoll.find_one(
            QuickRoll.id == quickroll_id,
            QuickRoll.is_archived == False,
        )
        if not quickroll:
            raise ValidationError(detail=f"Quick roll {quickroll_id} not found")
        return quickroll

    async def get_user_by_id(self, user_id: PydanticObjectId) -> User:
        """Get a user by ID."""
        user = await User.find_one(
            User.id == user_id,
            User.is_archived == False,
        )
        if not user:
            raise ValidationError(detail=f"User {user_id} not found")
        return user

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
        character_trait = await CharacterTrait.find_one(
            CharacterTrait.id == character_trait_id,
            fetch_links=fetch_links,
        )
        if not character_trait:
            raise ValidationError(detail=f"Character trait {character_trait_id} not found")
        return character_trait

    async def get_trait_by_id(self, trait_id: PydanticObjectId) -> Trait:
        """Get a trait by ID."""
        trait = await Trait.find_one(
            Trait.id == trait_id,
            Trait.is_archived == False,
        )
        if not trait:
            raise ValidationError(detail=f"Trait {trait_id} not found")
        return trait

    async def get_trait_category_by_id(self, trait_category_id: PydanticObjectId) -> TraitCategory:
        """Get a trait category by ID."""
        trait_category = await TraitCategory.find_one(
            TraitCategory.id == trait_category_id,
            TraitCategory.is_archived == False,
        )
        if not trait_category:
            raise ValidationError(detail=f"Trait category {trait_category_id} not found")
        return trait_category

    async def get_sheet_section_by_id(self, sheet_section_id: PydanticObjectId) -> CharSheetSection:
        """Get a sheet section by ID."""
        sheet_section = await CharSheetSection.find_one(
            CharSheetSection.id == sheet_section_id,
            CharSheetSection.is_archived == False,
        )
        if not sheet_section:
            raise ValidationError(detail=f"Sheet section {sheet_section_id} not found")
        return sheet_section
