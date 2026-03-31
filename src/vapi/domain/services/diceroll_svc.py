"""Diceroll services."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from beanie.operators import In
from pydantic import ValidationError as PydanticValidationError

from vapi.constants import DiceSize
from vapi.db.models import CharacterTrait, Company, DiceRoll, User
from vapi.domain.handlers.diceroll_handler import roll_dice
from vapi.domain.utils import validate_trait_ids_from_mixed_sources
from vapi.lib.exceptions import ValidationError
from vapi.utils.validation import raise_from_pydantic_validation_error

from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from vapi.domain.controllers.dicerolls import dto


class DiceRollService:
    """Diceroll service."""

    async def create_complete_dice_roll(self, dice_roll: DiceRoll) -> DiceRoll:
        """Roll the dice."""
        validation_svc = GetModelByIdValidationService()

        # Run independent validations concurrently
        coros: list = []
        if dice_roll.campaign_id:
            coros.append(validation_svc.get_campaign_by_id(dice_roll.campaign_id))
        if dice_roll.trait_ids:
            coros.append(validate_trait_ids_from_mixed_sources(dice_roll.trait_ids))
        if dice_roll.character_id:
            coros.append(validation_svc.get_character_by_id(dice_roll.character_id))

        results = await asyncio.gather(*coros) if coros else []

        # Extract validated trait_ids from results (it's the only result we need)
        dice_roll.trait_ids = next(
            (r for r in results if isinstance(r, list)),
            [],
        )

        dice_roll.result = roll_dice(
            num_dice=dice_roll.num_dice,
            num_desperation_dice=dice_roll.num_desperation_dice,
            difficulty=dice_roll.difficulty,
            dice_size=dice_roll.dice_size,
        )

        try:
            await dice_roll.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)
        return dice_roll

    async def roll_quickroll(
        self,
        *,
        company: Company,
        user: User,
        data: dto.QuickRollDTO,
    ) -> DiceRoll:
        """Roll a quick roll."""
        validation_svc = GetModelByIdValidationService()
        quickroll, character = await asyncio.gather(
            validation_svc.get_quickroll_by_id(data.quickroll_id),
            validation_svc.get_character_by_id(data.character_id),
        )

        traits_to_roll = await CharacterTrait.find(
            CharacterTrait.character_id == character.id,
            In(CharacterTrait.trait.id, quickroll.trait_ids),  # type: ignore [attr-defined]
            fetch_links=True,
        ).to_list()

        if not traits_to_roll:
            raise ValidationError(
                detail="This character does not have the traits required to roll this quick roll"
            )

        total_dice = sum(trait.value for trait in traits_to_roll)

        result = roll_dice(
            num_dice=total_dice,
            num_desperation_dice=data.num_desperation_dice,
            difficulty=data.difficulty,
            dice_size=DiceSize.D10,
        )

        try:
            dice_roll = DiceRoll(
                dice_size=DiceSize.D10,
                num_dice=total_dice,
                num_desperation_dice=data.num_desperation_dice,
                difficulty=data.difficulty,
                result=result,
                company_id=company.id,
                user_id=user.id,
                trait_ids=quickroll.trait_ids,
                character_id=character.id,
                campaign_id=character.campaign_id,
                comment=data.comment or f"Quick roll: {quickroll.name}",
            )
            await dice_roll.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)
        return dice_roll
