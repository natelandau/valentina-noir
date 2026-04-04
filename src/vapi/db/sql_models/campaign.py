"""Campaign, book, and chapter models."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from tortoise import fields
from tortoise.validators import MaxValueValidator, MinLengthValidator, MinValueValidator

from vapi.db.sql_models.base import BaseModel

if TYPE_CHECKING:
    from vapi.db.sql_models.character import Character
    from vapi.db.sql_models.chargen_session import ChargenSession
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.diceroll import DiceRoll
    from vapi.db.sql_models.notes import Note
    from vapi.db.sql_models.user import CampaignExperience


class Campaign(BaseModel):
    """A game campaign belonging to a company."""

    name = fields.CharField(max_length=50, validators=[MinLengthValidator(3)])
    description = fields.TextField(null=True, validators=[MinLengthValidator(3)])
    desperation = fields.IntField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    danger = fields.IntField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])

    _empty_string_to_none_fields: ClassVar[frozenset[str]] = frozenset({"description"})

    company: fields.ForeignKeyRelation[Company] = fields.ForeignKeyField(
        "models.Company", related_name="campaigns", on_delete=fields.OnDelete.CASCADE
    )

    # Reverse relations
    books: fields.ReverseRelation[CampaignBook]
    characters: fields.ReverseRelation[Character]
    user_experiences: fields.ReverseRelation[CampaignExperience]
    notes: fields.ReverseRelation[Note]
    dice_rolls: fields.ReverseRelation[DiceRoll]
    chargen_sessions: fields.ReverseRelation[ChargenSession]

    class Meta:
        """Tortoise ORM meta options."""

        table = "campaign"


class CampaignBook(BaseModel):
    """A book within a campaign."""

    name = fields.CharField(max_length=50)
    description = fields.TextField(null=True)
    number = fields.IntField()

    campaign: fields.ForeignKeyRelation[Campaign] = fields.ForeignKeyField(
        "models.Campaign", related_name="books", on_delete=fields.OnDelete.CASCADE
    )

    # Reverse relations
    chapters: fields.ReverseRelation[CampaignChapter]
    notes: fields.ReverseRelation[Note]

    class Meta:
        """Tortoise ORM meta options."""

        table = "campaign_book"


class CampaignChapter(BaseModel):
    """A chapter within a campaign book."""

    name = fields.CharField(max_length=50)
    description = fields.TextField(null=True)
    number = fields.IntField()

    book: fields.ForeignKeyRelation[CampaignBook] = fields.ForeignKeyField(
        "models.CampaignBook", related_name="chapters", on_delete=fields.OnDelete.CASCADE
    )

    # Reverse relations
    notes: fields.ReverseRelation[Note]

    class Meta:
        """Tortoise ORM meta options."""

        table = "campaign_chapter"
