"""Unit tests for dicerolls services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from beanie import PydanticObjectId

from vapi.constants import DiceSize
from vapi.db.models import (
    Campaign,
    Character,
    CharacterTrait,
    Company,
    DiceRoll,
    QuickRoll,
    Trait,
    User,
)
from vapi.domain.controllers.dicerolls.dto import QuickRollDTO
from vapi.domain.services import DiceRollService
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable
pytestmark = pytest.mark.anyio


class TestDiceRollService:
    """Test the dice roll service."""

    async def test_create_complete_dice_roll_minimal(
        self,
        debug: Callable[[Any], None],
    ) -> None:
        """Test the create_complete_dice_roll method."""
        # Given objects
        dice_roll = DiceRoll(
            user_id=PydanticObjectId(),
            company_id=PydanticObjectId(),
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            difficulty=6,
            trait_ids=[],
            character_id=None,
            campaign_id=None,
            comment=None,
        )

        # When we create the complete dice roll
        service = DiceRollService()
        result = await service.create_complete_dice_roll(dice_roll)

        # Then the dice roll is returned
        assert result.id is not None
        assert result.result is not None

    async def test_create_complete_dice_roll_every_field(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        campaign_factory: Callable[[dict[str, Any]], Campaign],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the create_complete_dice_roll method."""
        # Given objects
        character = await character_factory()
        campaign = await campaign_factory()
        traits = await Trait.find(Trait.is_archived == False).limit(2).to_list()
        dice_roll = DiceRoll(
            user_id=PydanticObjectId(),
            company_id=PydanticObjectId(),
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            difficulty=6,
            trait_ids=[trait.id for trait in traits],
            character_id=character.id,
            campaign_id=campaign.id,
            comment="Test comment",
        )

        # When we create the complete dice roll
        service = DiceRollService()
        result = await service.create_complete_dice_roll(dice_roll)

        # Then the dice roll is returned
        assert result.id is not None
        assert result.result is not None

    async def test_create_complete_dice_invalid_trait_ids(
        self,
        debug: Callable[[Any], None],
    ) -> None:
        """Test the create_complete_dice_roll method when the trait ids are invalid."""
        # Given objects
        dice_roll = DiceRoll(
            user_id=PydanticObjectId(),
            company_id=PydanticObjectId(),
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            difficulty=6,
            trait_ids=[PydanticObjectId()],
        )

        # When we create the complete dice roll
        service = DiceRollService()
        with pytest.raises(ValidationError, match="Trait not found"):
            await service.create_complete_dice_roll(dice_roll)

    async def test_create_complete_dice_roll_character_not_found(
        self,
        debug: Callable[[Any], None],
    ) -> None:
        """Test the create_complete_dice_roll method when the character is not found."""
        # Given objects
        dice_roll = DiceRoll(
            user_id=PydanticObjectId(),
            company_id=PydanticObjectId(),
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            difficulty=6,
            trait_ids=[],
            character_id=PydanticObjectId(),
            campaign_id=None,
            comment=None,
        )

        # When we create the complete dice roll
        service = DiceRollService()
        with pytest.raises(ValidationError, match=r"Character.*not found"):
            await service.create_complete_dice_roll(dice_roll)

    async def test_create_complete_dice_roll_campaign_not_found(
        self,
        debug: Callable[[Any], None],
    ) -> None:
        """Test the create_complete_dice_roll method when the campaign is not found."""
        # Given objects
        dice_roll = DiceRoll(
            user_id=PydanticObjectId(),
            company_id=PydanticObjectId(),
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            difficulty=6,
            trait_ids=[],
            character_id=None,
            campaign_id=PydanticObjectId(),
            comment=None,
        )

        # When we create the complete dice roll
        service = DiceRollService()
        with pytest.raises(ValidationError, match=r"Campaign.*not found"):
            await service.create_complete_dice_roll(dice_roll)

    async def test_roll_quickroll(
        self,
        quickroll_factory: Callable[[dict[str, Any]], QuickRoll],
        character_factory: Callable[[dict[str, Any]], Character],
        campaign_factory: Callable[[dict[str, Any]], Campaign],
        company_factory: Callable[[dict[str, Any]], Company],
        user_factory: Callable[[dict[str, Any]], User],
        character_trait_factory: Callable[[dict[str, Any]], CharacterTrait],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the roll_quickroll method."""
        # Given objects
        company = await company_factory()
        user = await user_factory()
        quickroll = await quickroll_factory()
        campaign = await campaign_factory()
        character = await character_factory(campaign_id=campaign.id)
        for trait in quickroll.trait_ids:
            await character_trait_factory(character_id=character.id, trait_id=trait)

        data = QuickRollDTO(
            quickroll_id=quickroll.id,
            character_id=character.id,
            comment="Test comment",
        )

        # when we roll the quickroll
        service = DiceRollService()
        result = await service.roll_quickroll(company=company, user=user, data=data)

        # then the dice roll is returned
        assert result.id is not None
        assert result.result is not None
        assert result.company_id == company.id
        assert result.user_id == user.id
        assert result.character_id == character.id
        assert result.campaign_id == campaign.id
        assert result.comment == "Test comment"
        assert result.trait_ids == quickroll.trait_ids
        assert result.difficulty == 6
        assert result.dice_size == DiceSize.D10

    async def test_roll_quickroll_no_matching_traits(
        self,
        quickroll_factory: Callable[[dict[str, Any]], QuickRoll],
        character_factory: Callable[[dict[str, Any]], Character],
        campaign_factory: Callable[[dict[str, Any]], Campaign],
        company_factory: Callable[[dict[str, Any]], Company],
        user_factory: Callable[[dict[str, Any]], User],
        character_trait_factory: Callable[[dict[str, Any]], CharacterTrait],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the roll_quickroll method when no matching traits are found."""
        # Given objects
        company = await company_factory()
        user = await user_factory()
        quickroll = await quickroll_factory()
        campaign = await campaign_factory()
        character = await character_factory(campaign_id=campaign.id)

        data = QuickRollDTO(
            quickroll_id=quickroll.id,
            character_id=character.id,
            comment="Test comment",
        )

        # when we roll the quickroll
        service = DiceRollService()
        with pytest.raises(ValidationError, match="No matching traits found to roll"):
            await service.roll_quickroll(company=company, user=user, data=data)
