"""Diceroll services."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from vapi.constants import MAX_NUM_DICE, CharacterType, DiceSize
from vapi.db.sql_models.character import Character, CharacterTrait
from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.diceroll import DiceRoll, DiceRollResult
from vapi.domain.handlers.diceroll_handlers import roll_dice
from vapi.lib.exceptions import PermissionDeniedError, ValidationError
from vapi.lib.guards import STORYTELLER_ROLES

from .validation_svc import (
    GetModelByIdValidationService,
    validate_trait_ids_from_mixed_sources,
)

if TYPE_CHECKING:
    from uuid import UUID

    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.user import User
    from vapi.domain.controllers.dicerolls import dto


def _assert_can_roll_for_character(*, character: Character, user: User) -> None:
    """Reject rolls against STORYTELLER characters unless the user is a storyteller or admin.

    Path guards cannot see a ``character_id`` sent in the request body, so the service enforces
    the same visibility rule they apply.
    """
    if character.type == CharacterType.STORYTELLER and user.role not in STORYTELLER_ROLES:
        raise PermissionDeniedError(detail="No rights to access this resource")


def _assert_campaign_matches_character(*, character: Character, campaign_id: UUID | None) -> None:
    """Reject a roll filed under a campaign other than its character's campaign."""
    character_campaign_id = character.campaign_id  # ty:ignore[unresolved-attribute]
    if campaign_id and character_campaign_id and campaign_id != character_campaign_id:
        msg = "campaign_id must match the character's campaign"
        raise ValidationError(
            detail=msg, invalid_parameters=[{"field": "campaign_id", "message": msg}]
        )


class DiceRollService:
    """Diceroll service."""

    async def create_complete_dice_roll(
        self,
        *,
        data: dto.DiceRollCreate,
        company_id: UUID,
        user: User,
    ) -> DiceRoll:
        """Create a dice roll with validation and result generation."""
        validation_svc = GetModelByIdValidationService()

        coros: list = []
        if data.campaign_id:
            coros.append(validation_svc.get_campaign_by_id(data.campaign_id, company_id=company_id))
        if data.character_id:
            coros.append(
                validation_svc.get_character_by_id(data.character_id, company_id=company_id)
            )
        if data.trait_ids:
            coros.append(
                validate_trait_ids_from_mixed_sources(data.trait_ids, company_id=company_id)
            )

        results = await asyncio.gather(*coros) if coros else []

        validated_trait_ids: list[UUID] = next(
            (r for r in results if isinstance(r, list)),
            [],
        )
        character = next((r for r in results if isinstance(r, Character)), None)
        if character is not None:
            _assert_can_roll_for_character(character=character, user=user)
            _assert_campaign_matches_character(character=character, campaign_id=data.campaign_id)

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
            user_id=user.id,
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
            validation_svc.get_quickroll_by_id(data.quickroll_id, company_id=company.id),
            validation_svc.get_character_by_id(data.character_id, company_id=company.id),
        )

        _assert_can_roll_for_character(character=character, user=user)

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
        if total_dice > MAX_NUM_DICE:
            raise ValidationError(
                detail=f"This quick roll builds a pool of {total_dice} dice; the maximum is {MAX_NUM_DICE}"
            )

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
            campaign_id=character.campaign_id,  # ty:ignore[unresolved-attribute]
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

        if quickroll.traits:
            await dice_roll.traits.add(*quickroll.traits)

        return await DiceRoll.get(id=dice_roll.id).prefetch_related("roll_result", "traits")
