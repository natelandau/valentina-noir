"""Unit tests for dicerolls services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from vapi.constants import MAX_NUM_DICE, CharacterType, DiceSize, UserRole
from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.diceroll import DiceRoll
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
        assert result.dice_modifier == 0

    async def test_create_complete_dice_roll_applies_modifier(
        self, company_factory: Callable[..., Any], user_factory: Callable[..., Any]
    ) -> None:
        """Verify the modifier changes the rolled pool but not the stored num_dice."""
        # Given a request for 4 dice with a +1 modifier
        company = await company_factory()
        user = await user_factory(company=company)
        data = DiceRollCreate(num_dice=4, dice_modifier=1, difficulty=6)

        # When creating the roll
        result = await DiceRollService().create_complete_dice_roll(
            data=data, company_id=company.id, user=user
        )

        # Then 5 dice are rolled and both inputs are stored
        assert len(result.roll_result.player_roll) == 5
        assert result.num_dice == 4
        assert result.dice_modifier == 1

    async def test_create_complete_dice_roll_modifier_to_zero_dice(
        self, company_factory: Callable[..., Any], user_factory: Callable[..., Any]
    ) -> None:
        """Verify a modifier may reduce the pool to exactly 0."""
        # Given a request for 2 dice with a -2 modifier
        company = await company_factory()
        user = await user_factory(company=company)
        data = DiceRollCreate(num_dice=2, dice_modifier=-2, difficulty=6)

        # When creating the roll
        result = await DiceRollService().create_complete_dice_roll(
            data=data, company_id=company.id, user=user
        )

        # Then no player dice are rolled
        assert result.roll_result.player_roll == []

    async def test_create_complete_dice_roll_modifier_below_zero_rejected(
        self, company_factory: Callable[..., Any], user_factory: Callable[..., Any]
    ) -> None:
        """Verify a modifier that makes the pool negative is rejected and nothing is stored."""
        # Given a request for 2 dice with a -3 modifier
        company = await company_factory()
        user = await user_factory(company=company)
        data = DiceRollCreate(num_dice=2, dice_modifier=-3, difficulty=6)
        before = await DiceRoll.filter().count()

        # When creating the roll
        # Then it is rejected without saving a roll
        with pytest.raises(ValidationError, match="below 0"):
            await DiceRollService().create_complete_dice_roll(
                data=data, company_id=company.id, user=user
            )
        assert await DiceRoll.filter().count() == before

    async def test_create_complete_dice_roll_modifier_over_maximum_rejected(
        self, company_factory: Callable[..., Any], user_factory: Callable[..., Any]
    ) -> None:
        """Verify a modifier that pushes the pool past the maximum is rejected."""
        # Given a maximum pool with a +1 modifier
        company = await company_factory()
        user = await user_factory(company=company)
        data = DiceRollCreate(num_dice=MAX_NUM_DICE, dice_modifier=1, difficulty=6)

        # When creating the roll
        # Then it is rejected
        with pytest.raises(ValidationError, match="maximum"):
            await DiceRollService().create_complete_dice_roll(
                data=data, company_id=company.id, user=user
            )

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

    async def _quickroll_setup(
        self,
        *,
        values: list[int],
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        campaign_factory: Callable[..., Any],
        character_factory: Callable[..., Any],
        character_trait_factory: Callable[..., Any],
        quickroll_factory: Callable[..., Any],
    ) -> tuple[Any, Any, Any, Any]:
        """Build a character whose quickroll traits have the given values."""
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company)
        character = await character_factory(company=company, campaign=campaign)
        traits = list(await Trait.filter(is_archived=False).limit(len(values)))
        for trait, value in zip(traits, values, strict=True):
            await character_trait_factory(character=character, trait=trait, value=value)
        quickroll = await quickroll_factory(user=user, traits=traits)
        return company, user, character, quickroll

    async def test_roll_quickroll_applies_modifier(
        self,
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        campaign_factory: Callable[..., Any],
        character_factory: Callable[..., Any],
        character_trait_factory: Callable[..., Any],
        quickroll_factory: Callable[..., Any],
    ) -> None:
        """Verify a quickroll modifier adds dice and is stored beside the base pool."""
        # Given traits summing to 4
        company, user, character, quickroll = await self._quickroll_setup(
            values=[2, 2],
            company_factory=company_factory,
            user_factory=user_factory,
            campaign_factory=campaign_factory,
            character_factory=character_factory,
            character_trait_factory=character_trait_factory,
            quickroll_factory=quickroll_factory,
        )
        data = QuickRollRequest(
            quickroll_id=quickroll.id, character_id=character.id, dice_modifier=1
        )

        # When rolling with a +1 modifier
        result = await DiceRollService().roll_quickroll(company=company, user=user, data=data)

        # Then 5 dice are rolled and the base pool and modifier are stored
        assert len(result.roll_result.player_roll) == 5
        assert result.num_dice == 4
        assert result.dice_modifier == 1

    async def test_roll_quickroll_modifier_below_zero_rejected(
        self,
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        campaign_factory: Callable[..., Any],
        character_factory: Callable[..., Any],
        character_trait_factory: Callable[..., Any],
        quickroll_factory: Callable[..., Any],
    ) -> None:
        """Verify a quickroll modifier that makes the pool negative is rejected."""
        # Given traits summing to 2
        company, user, character, quickroll = await self._quickroll_setup(
            values=[1, 1],
            company_factory=company_factory,
            user_factory=user_factory,
            campaign_factory=campaign_factory,
            character_factory=character_factory,
            character_trait_factory=character_trait_factory,
            quickroll_factory=quickroll_factory,
        )
        data = QuickRollRequest(
            quickroll_id=quickroll.id, character_id=character.id, dice_modifier=-3
        )

        before = await DiceRoll.filter().count()

        # When rolling with a -3 modifier
        # Then it is rejected without saving a roll
        with pytest.raises(ValidationError, match="below 0"):
            await DiceRollService().roll_quickroll(company=company, user=user, data=data)
        assert await DiceRoll.filter().count() == before

    async def test_roll_quickroll_modifier_brings_pool_under_maximum(
        self,
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        campaign_factory: Callable[..., Any],
        character_factory: Callable[..., Any],
        character_trait_factory: Callable[..., Any],
        quickroll_factory: Callable[..., Any],
    ) -> None:
        """Verify a negative modifier can bring an oversized base pool within the maximum."""
        # Given traits summing to the maximum plus 2
        company, user, character, quickroll = await self._quickroll_setup(
            values=[MAX_NUM_DICE // 2 + 2, MAX_NUM_DICE - MAX_NUM_DICE // 2],
            company_factory=company_factory,
            user_factory=user_factory,
            campaign_factory=campaign_factory,
            character_factory=character_factory,
            character_trait_factory=character_trait_factory,
            quickroll_factory=quickroll_factory,
        )
        data = QuickRollRequest(
            quickroll_id=quickroll.id, character_id=character.id, dice_modifier=-2
        )

        # When rolling with a -2 modifier
        result = await DiceRollService().roll_quickroll(company=company, user=user, data=data)

        # Then the roll succeeds with the maximum pool
        assert len(result.roll_result.player_roll) == MAX_NUM_DICE

    @pytest.mark.parametrize(
        ("values", "dice_modifier"),
        [
            ([MAX_NUM_DICE // 2 + 1, MAX_NUM_DICE // 2 + 1], 0),
            ([MAX_NUM_DICE // 2, MAX_NUM_DICE - 1 - MAX_NUM_DICE // 2], 2),
        ],
        ids=["trait_sum_over_maximum", "modifier_pushes_pool_over_maximum"],
    )
    async def test_roll_quickroll_rejects_pool_over_maximum(
        self,
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        campaign_factory: Callable[..., Any],
        character_factory: Callable[..., Any],
        character_trait_factory: Callable[..., Any],
        quickroll_factory: Callable[..., Any],
        values: list[int],
        dice_modifier: int,
    ) -> None:
        """Verify a quickroll pool past the dice maximum is rejected, with or without a modifier."""
        # Given traits that sum past the maximum, alone or once the modifier is added
        company, user, character, quickroll = await self._quickroll_setup(
            values=values,
            company_factory=company_factory,
            user_factory=user_factory,
            campaign_factory=campaign_factory,
            character_factory=character_factory,
            character_trait_factory=character_trait_factory,
            quickroll_factory=quickroll_factory,
        )
        data = QuickRollRequest(
            quickroll_id=quickroll.id, character_id=character.id, dice_modifier=dice_modifier
        )

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
