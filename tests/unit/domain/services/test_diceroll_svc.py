"""Unit tests for dicerolls services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from vapi.constants import MAX_NUM_DICE, CharacterType, DiceSize, UserRole
from vapi.db.sql_models.character_sheet import Trait
from vapi.domain.controllers.dicerolls.dto import DiceRollCreate, QuickRollRequest
from vapi.domain.services import DiceRollService
from vapi.lib.exceptions import PermissionDeniedError, ValidationError

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
            data=data, company_id=company.id, user=user
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
            data=data, company_id=company.id, user=user
        )

        # Then the dice roll is returned with a result
        assert result.id is not None
        assert result.roll_result is not None

    @pytest.mark.parametrize(
        ("extra_kwargs", "error_match"),
        [
            ({"trait_ids": [uuid4()]}, "Trait not found"),
            ({"character_id": uuid4()}, r"Character.*not found"),
            ({"campaign_id": uuid4()}, r"Campaign.*not found"),
        ],
        ids=["invalid_trait_ids", "character_not_found", "campaign_not_found"],
    )
    async def test_create_complete_dice_roll_invalid_references(
        self,
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        debug: Callable[[Any], None],
        extra_kwargs: dict,
        error_match: str,
    ) -> None:
        """Verify creating a dice roll with a nonexistent reference raises a ValidationError."""
        # Given a company and user
        company = await company_factory()
        user = await user_factory(company=company)
        data = DiceRollCreate(
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            difficulty=6,
            **extra_kwargs,
        )

        # When we create the complete dice roll
        service = DiceRollService()
        with pytest.raises(ValidationError, match=error_match):
            await service.create_complete_dice_roll(data=data, company_id=company.id, user=user)

    async def test_create_complete_dice_roll_rejects_mismatched_campaign(
        self,
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        character_factory: Callable[..., Any],
        campaign_factory: Callable[..., Any],
    ) -> None:
        """Verify a campaign_id that differs from the character's campaign is rejected."""
        # Given a character in one campaign and a second campaign in the same company
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company)
        other_campaign = await campaign_factory(company=company)
        character = await character_factory(company=company, campaign=campaign)
        data = DiceRollCreate(
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            difficulty=6,
            character_id=character.id,
            campaign_id=other_campaign.id,
        )

        # When we create the dice roll
        # Then a ValidationError is raised
        with pytest.raises(ValidationError, match="must match the character's campaign"):
            await DiceRollService().create_complete_dice_roll(
                data=data, company_id=company.id, user=user
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
        assert result.company_id == company.id
        assert result.user_id == user.id
        assert result.character_id == character.id
        assert result.campaign_id == campaign.id
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

    async def test_roll_quickroll_rejects_pool_over_maximum(
        self,
        quickroll_factory: Callable[..., Any],
        character_factory: Callable[..., Any],
        campaign_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        character_trait_factory: Callable[..., Any],
    ) -> None:
        """Verify a quickroll whose traits sum past the dice maximum is rejected."""
        # Given a character whose quickroll traits add up to more than the maximum pool
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company)
        character = await character_factory(company=company, campaign=campaign)
        traits = await Trait.filter(is_archived=False).limit(2)
        for trait in traits:
            await character_trait_factory(
                character=character, trait=trait, value=MAX_NUM_DICE // 2 + 1
            )
        quickroll = await quickroll_factory(user=user, traits=list(traits))
        data = QuickRollRequest(quickroll_id=quickroll.id, character_id=character.id)

        # When rolling the quickroll
        # Then the oversized pool is rejected
        with pytest.raises(ValidationError, match="maximum"):
            await DiceRollService().roll_quickroll(company=company, user=user, data=data)


class TestStorytellerCharacterRolls:
    """Verify only storytellers and admins can roll for STORYTELLER characters."""

    @pytest.mark.parametrize(
        ("role", "allowed"),
        [(UserRole.PLAYER, False), (UserRole.STORYTELLER, True), (UserRole.ADMIN, True)],
    )
    async def test_create_dice_roll_for_storyteller_character(
        self,
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        character_factory: Callable[..., Any],
        role: UserRole,
        allowed: bool,
    ) -> None:
        """Verify creating a roll against a STORYTELLER character requires a storyteller role."""
        # Given a STORYTELLER character and a user with the given role
        company = await company_factory()
        user = await user_factory(company=company, role=role)
        character = await character_factory(company=company, type=CharacterType.STORYTELLER)
        data = DiceRollCreate(num_dice=3, character_id=character.id)
        service = DiceRollService()

        # When the user rolls for the character
        # Then players are denied and storytellers or admins succeed
        if allowed:
            result = await service.create_complete_dice_roll(
                data=data, company_id=company.id, user=user
            )
            assert result.character_id == character.id
        else:
            with pytest.raises(PermissionDeniedError):
                await service.create_complete_dice_roll(data=data, company_id=company.id, user=user)

    @pytest.mark.parametrize(
        ("role", "allowed"),
        [(UserRole.PLAYER, False), (UserRole.STORYTELLER, True)],
    )
    async def test_quickroll_for_storyteller_character(
        self,
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        character_factory: Callable[..., Any],
        character_trait_factory: Callable[..., Any],
        quickroll_factory: Callable[..., Any],
        role: UserRole,
        allowed: bool,
    ) -> None:
        """Verify a quick roll against a STORYTELLER character requires a storyteller role."""
        # Given a STORYTELLER character with a trait and a quick roll that uses it
        company = await company_factory()
        user = await user_factory(company=company, role=role)
        character = await character_factory(company=company, type=CharacterType.STORYTELLER)
        trait = await Trait.filter(is_archived=False, custom_for_character_id__isnull=True).first()
        await character_trait_factory(character=character, trait=trait, value=3)
        quickroll = await quickroll_factory(user=user, traits=[trait])
        data = QuickRollRequest(quickroll_id=quickroll.id, character_id=character.id)
        service = DiceRollService()

        # When the user rolls the quick roll for the character
        # Then players are denied and storytellers succeed
        if allowed:
            result = await service.roll_quickroll(company=company, user=user, data=data)
            assert result.num_dice == 3
        else:
            with pytest.raises(PermissionDeniedError):
                await service.roll_quickroll(company=company, user=user, data=data)
