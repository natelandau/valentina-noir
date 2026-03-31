"""Note model — attached to various parent entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields

from vapi.db.sql_models.base import BaseModel

if TYPE_CHECKING:
    from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
    from vapi.db.sql_models.character import Character
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.user import User


class Note(BaseModel):
    """A note attached to a user, campaign, book, chapter, or character."""

    title = fields.CharField(max_length=50)
    content = fields.TextField()

    company: fields.ForeignKeyRelation[Company] = fields.ForeignKeyField(
        "models.Company", related_name="notes", on_delete=fields.OnDelete.CASCADE
    )
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="notes", on_delete=fields.OnDelete.SET_NULL, null=True
    )
    campaign: fields.ForeignKeyRelation[Campaign] = fields.ForeignKeyField(
        "models.Campaign", related_name="notes", on_delete=fields.OnDelete.SET_NULL, null=True
    )
    book: fields.ForeignKeyRelation[CampaignBook] = fields.ForeignKeyField(
        "models.CampaignBook", related_name="notes", on_delete=fields.OnDelete.SET_NULL, null=True
    )
    chapter: fields.ForeignKeyRelation[CampaignChapter] = fields.ForeignKeyField(
        "models.CampaignChapter",
        related_name="notes",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )
    character: fields.ForeignKeyRelation[Character] = fields.ForeignKeyField(
        "models.Character",
        related_name="notes",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )

    class Meta:
        """Tortoise ORM meta options."""

        table = "note"
