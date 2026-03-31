"""Dice roll model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tortoise import fields

from vapi.constants import DiceSize
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
    result: Any = fields.JSONField(null=True)
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

    # M2M
    traits: fields.ManyToManyRelation[Trait] = fields.ManyToManyField(
        "models.Trait", related_name="dice_rolls", through="dice_roll_traits"
    )

    class Meta:
        """Tortoise ORM meta options."""

        table = "dice_roll"
