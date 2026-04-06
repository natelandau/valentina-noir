"""Unit tests for dicerolls services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from vapi.constants import DiceSize
from vapi.db.sql_models.character_sheet import Trait
from vapi.domain.controllers.dicerolls.dto import DiceRollCreate, QuickRollRequest
from vapi.domain.services import DiceRollService
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


class TestDiceRollService:
    """Test the dice roll service."""

    async def test_create_complete_dice_roll_minimal(
        self,
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify creating a dice roll with minimal fields."""
        # Given a company and user
        company = await company_factory()
        user = await user_factory(company=company)
        data = DiceRollCreate(
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            difficulty=6,
        )

        # When we create the complete dice roll
        service = DiceRollService()
        result = await service.create_complete_dice_roll(
            data=data, company_id=company.id, user_id=user.id
        )

        # Then the dice roll is returned with a result
        assert result.id is not None
        assert result.roll_result is not None

    async def test_create_complete_dice_roll_every_field(
        self,
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        character_factory: Callable[..., Any],
        campaign_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify creating a dice roll with all fields populated."""
        # Given objects
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company)
        character = await character_factory(company=company, campaign=campaign)
        traits = await Trait.filter(is_archived=False).limit(2)

        data = DiceRollCreate(
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
        result = await service.create_complete_dice_roll(
            data=data, company_id=company.id, user_id=user.id
        )

        # Then the dice roll is returned with a result
        assert result.id is not None
        assert result.roll_result is not None

    async def test_create_complete_dice_invalid_trait_ids(
        self,
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify creating a dice roll with invalid trait IDs raises an error."""
        # Given a company and user
        company = await company_factory()
        user = await user_factory(company=company)
        data = DiceRollCreate(
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            difficulty=6,
            trait_ids=[uuid4()],
        )

        # When we create the complete dice roll
        service = DiceRollService()
        with pytest.raises(ValidationError, match="Trait not found"):
            await service.create_complete_dice_roll(
                data=data, company_id=company.id, user_id=user.id
            )

    async def test_create_complete_dice_roll_character_not_found(
        self,
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify creating a dice roll with a nonexistent character raises an error."""
        # Given a company and user
        company = await company_factory()
        user = await user_factory(company=company)
        data = DiceRollCreate(
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            difficulty=6,
            character_id=uuid4(),
        )

        # When we create the complete dice roll
        service = DiceRollService()
        with pytest.raises(ValidationError, match=r"Character.*not found"):
            await service.create_complete_dice_roll(
                data=data, company_id=company.id, user_id=user.id
            )

    async def test_create_complete_dice_roll_campaign_not_found(
        self,
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify creating a dice roll with a nonexistent campaign raises an error."""
        # Given a company and user
        company = await company_factory()
        user = await user_factory(company=company)
        data = DiceRollCreate(
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            difficulty=6,
            campaign_id=uuid4(),
        )

        # When we create the complete dice roll
        service = DiceRollService()
        with pytest.raises(ValidationError, match=r"Campaign.*not found"):
            await service.create_complete_dice_roll(
                data=data, company_id=company.id, user_id=user.id
            )

    async def test_roll_quickroll(
        self,
        quickroll_factory: Callable[..., Any],
        character_factory: Callable[..., Any],
        campaign_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        character_trait_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify rolling a quickroll creates a dice roll with expected fields."""
        # Given objects
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company)
        character = await character_factory(company=company, campaign=campaign)

        # Create character traits with distinct traits
        traits = await Trait.filter(is_archived=False).limit(2)
        ct1 = await character_trait_factory(character=character, trait=traits[0])
        ct2 = await character_trait_factory(character=character, trait=traits[1])
        await ct1.fetch_related("trait")
        await ct2.fetch_related("trait")

        # Create quickroll with the same traits
        quickroll = await quickroll_factory(user=user, traits=[ct1.trait, ct2.trait])

        data = QuickRollRequest(
            quickroll_id=quickroll.id,
            character_id=character.id,
            comment="Test comment",
        )

        # When we roll the quickroll
        service = DiceRollService()
        result = await service.roll_quickroll(company=company, user=user, data=data)

        # Then the dice roll is returned with correct fields
        assert result.id is not None
        assert result.roll_result is not None
        assert result.company_id == company.id  # type: ignore[attr-defined]
        assert result.user_id == user.id  # type: ignore[attr-defined]
        assert result.character_id == character.id  # type: ignore[attr-defined]
        assert result.campaign_id == campaign.id  # type: ignore[attr-defined]
        assert result.comment == "Test comment"
        # Verify traits match the ones we set up
        result_trait_ids = sorted(t.id for t in result.traits)
        expected_trait_ids = sorted([ct1.trait.id, ct2.trait.id])
        assert result_trait_ids == expected_trait_ids
        assert result.difficulty == 6

    async def test_roll_quickroll_no_matching_traits(
        self,
        quickroll_factory: Callable[..., Any],
        character_factory: Callable[..., Any],
        campaign_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify rolling a quickroll with no matching traits raises an error."""
        # Given a character with no traits matching the quickroll
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company)
        character = await character_factory(company=company, campaign=campaign)

        # Create quickroll with some traits, but don't add them to the character
        traits = await Trait.filter(is_archived=False).limit(2)
        quickroll = await quickroll_factory(user=user, traits=list(traits))

        data = QuickRollRequest(
            quickroll_id=quickroll.id,
            character_id=character.id,
            comment="Test comment",
        )

        # When we roll the quickroll
        service = DiceRollService()
        with pytest.raises(
            ValidationError,
            match="This character does not have the traits required to roll this quick rol",
        ):
            await service.roll_quickroll(company=company, user=user, data=data)
