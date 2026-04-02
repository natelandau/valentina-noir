"""Dice roll model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.contrib.postgres.fields import ArrayField

from vapi.constants import DiceSize, RollResultType
from vapi.db.sql_models.base import BaseModel

if TYPE_CHECKING:
    from vapi.db.sql_models.campaign import Campaign
    from vapi.db.sql_models.character import Character
    from vapi.db.sql_models.character_sheet import Trait
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.user import User


class DiceRoll(BaseModel):
    """A recorded dice roll."""

    difficulty = fields.IntField(null=True)
    dice_size = fields.IntEnumField(DiceSize)
    num_dice = fields.IntField()
    num_desperation_dice = fields.IntField(default=0)
    comment = fields.TextField(null=True)

    company: fields.ForeignKeyRelation[Company] = fields.ForeignKeyField(
        "models.Company", related_name="dice_rolls", on_delete=fields.OnDelete.CASCADE
    )
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="dice_rolls", on_delete=fields.OnDelete.SET_NULL, null=True
    )
    character: fields.ForeignKeyRelation[Character] = fields.ForeignKeyField(
        "models.Character",
        related_name="dice_rolls",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )
    campaign: fields.ForeignKeyRelation[Campaign] = fields.ForeignKeyField(
        "models.Campaign",
        related_name="dice_rolls",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )

    # Reverse relation
    roll_result: fields.ReverseRelation[DiceRollResult]

    # M2M
    traits: fields.ManyToManyRelation[Trait] = fields.ManyToManyField(
        "models.Trait", related_name="dice_rolls", through="dice_roll_traits"
    )

    class Meta:
        """Tortoise ORM meta options."""

        table = "dice_roll"


class DiceRollResult(BaseModel):
    """Result data for a dice roll."""

    dice_roll: fields.OneToOneRelation[DiceRoll] = fields.OneToOneField(
        "models.DiceRoll", related_name="roll_result", on_delete=fields.OnDelete.CASCADE
    )
    total_result = fields.IntField(null=True)
    total_result_type = fields.CharEnumField(RollResultType, db_index=True)
    total_result_humanized = fields.CharField(max_length=255)
    total_dice_roll = ArrayField(element_type="int")
    player_roll = ArrayField(element_type="int")
    desperation_roll = ArrayField(element_type="int")

    class Meta:
        """Tortoise ORM meta options."""

        table = "dice_roll_result"
