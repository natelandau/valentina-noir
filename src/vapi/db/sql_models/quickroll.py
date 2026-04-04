"""Quick roll model -saved dice roll templates."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from tortoise import fields
from tortoise.validators import MinLengthValidator

from vapi.db.sql_models.base import BaseModel

if TYPE_CHECKING:
    from vapi.db.sql_models.character_sheet import Trait
    from vapi.db.sql_models.user import User


class QuickRoll(BaseModel):
    """A saved dice roll template for quick access."""

    name = fields.CharField(max_length=50, validators=[MinLengthValidator(3)])
    description = fields.TextField(null=True, validators=[MinLengthValidator(3)])

    _empty_string_to_none_fields: ClassVar[frozenset[str]] = frozenset({"description"})

    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="quick_rolls", on_delete=fields.OnDelete.CASCADE
    )

    # M2M
    traits: fields.ManyToManyRelation[Trait] = fields.ManyToManyField(
        "models.Trait", related_name="quick_rolls", through="quick_roll_traits"
    )

    class Meta:
        """Tortoise ORM meta options."""

        table = "quick_roll"
