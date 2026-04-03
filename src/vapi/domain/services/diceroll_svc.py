"""Diceroll services."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from vapi.constants import DiceSize
from vapi.db.sql_models.character import CharacterTrait
from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.diceroll import DiceRoll, DiceRollResult
from vapi.domain.handlers.diceroll_handler import roll_dice
from vapi.domain.utils import validate_trait_ids_from_mixed_sources
from vapi.lib.exceptions import ValidationError

from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from uuid import UUID

    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.user import User
    from vapi.domain.controllers.dicerolls import dto


class DiceRollService:
    """Diceroll service."""

    async def create_complete_dice_roll(
        self,
        *,
        data: dto.DiceRollCreate,
        company_id: UUID,
        user_id: UUID,
    ) -> DiceRoll:
        """Create a dice roll with validation and result generation."""
        validation_svc = GetModelByIdValidationService()

        coros: list = []
        if data.campaign_id:
            coros.append(validation_svc.get_campaign_by_id(data.campaign_id))
        if data.character_id:
            coros.append(validation_svc.get_character_by_id(data.character_id))
        if data.trait_ids:
            coros.append(validate_trait_ids_from_mixed_sources(data.trait_ids))

        results = await asyncio.gather(*coros) if coros else []

        validated_trait_ids: list[UUID] = next(
            (r for r in results if isinstance(r, list)),
            [],
        )

        result = roll_dice(
            num_dice=data.num_dice,
            num_desperation_dice=data.num_desperation_dice,
            difficulty=data.difficulty,
            dice_size=data.dice_size,
        )

        dice_roll = await DiceRoll.create(
            difficulty=data.difficulty,
            dice_size=data.dice_size,
            num_dice=data.num_dice,
            num_desperation_dice=data.num_desperation_dice,
            comment=data.comment,
            company_id=company_id,
            user_id=user_id,
            campaign_id=data.campaign_id,
            character_id=data.character_id,
        )

        await DiceRollResult.create(
            dice_roll=dice_roll,
            total_result=result.total_result,
            total_result_type=result.total_result_type,
            total_result_humanized=result.total_result_humanized,
            total_dice_roll=result.total_dice_roll,
            player_roll=result.player_roll,
            desperation_roll=result.desperation_roll,
        )

        if validated_trait_ids:
            traits = await Trait.filter(id__in=validated_trait_ids)
            await dice_roll.traits.add(*traits)

        # Re-fetch to populate relations
        return await DiceRoll.get(id=dice_roll.id).prefetch_related("roll_result", "traits")

    async def roll_quickroll(
        self,
        *,
        company: Company,
        user: User,
        data: dto.QuickRollRequest,
    ) -> DiceRoll:
        """Roll a quick roll."""
        validation_svc = GetModelByIdValidationService()
        quickroll, character = await asyncio.gather(
            validation_svc.get_quickroll_by_id(data.quickroll_id),
            validation_svc.get_character_by_id(data.character_id),
        )

        await quickroll.fetch_related("traits")
        quickroll_trait_ids = [t.id for t in quickroll.traits]

        traits_to_roll = await CharacterTrait.filter(
            character=character,
            trait_id__in=quickroll_trait_ids,
        ).prefetch_related("trait")

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

        dice_roll = await DiceRoll.create(
            dice_size=DiceSize.D10,
            num_dice=total_dice,
            num_desperation_dice=data.num_desperation_dice,
            difficulty=data.difficulty,
            company=company,
            user=user,
            character=character,
            campaign_id=character.campaign_id,  # type: ignore[attr-defined]
            comment=data.comment or f"Quick roll: {quickroll.name}",
        )

        await DiceRollResult.create(
            dice_roll=dice_roll,
            total_result=result.total_result,
            total_result_type=result.total_result_type,
            total_result_humanized=result.total_result_humanized,
            total_dice_roll=result.total_dice_roll,
            player_roll=result.player_roll,
            desperation_roll=result.desperation_roll,
        )

        if quickroll_trait_ids:
            trait_objects = await Trait.filter(id__in=quickroll_trait_ids)
            await dice_roll.traits.add(*trait_objects)

        return await DiceRoll.get(id=dice_roll.id).prefetch_related("roll_result", "traits")
