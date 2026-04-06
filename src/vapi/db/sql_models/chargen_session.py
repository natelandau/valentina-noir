"""Character generation session model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields

from vapi.db.sql_models.base import BaseModel

if TYPE_CHECKING:
    from vapi.db.sql_models.campaign import Campaign
    from vapi.db.sql_models.character import Character
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.user import User


class ChargenSession(BaseModel):
    """A character generation session tracking user choices."""

    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="chargen_sessions", on_delete=fields.OnDelete.CASCADE
    )
    company: fields.ForeignKeyRelation[Company] = fields.ForeignKeyField(
        "models.Company", related_name="chargen_sessions", on_delete=fields.OnDelete.CASCADE
    )
    campaign: fields.ForeignKeyRelation[Campaign] = fields.ForeignKeyField(
        "models.Campaign", related_name="chargen_sessions", on_delete=fields.OnDelete.CASCADE
    )
    expires_at = fields.DatetimeField()
    requires_selection = fields.BooleanField(default=False)

    # M2M
    characters: fields.ManyToManyRelation[Character] = fields.ManyToManyField(
        "models.Character",
        related_name="chargen_sessions",
        through="chargen_session_characters",
    )

    class Meta:
        """Tortoise ORM meta options."""

        table = "chargen_session"
