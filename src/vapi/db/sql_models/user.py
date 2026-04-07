"""User and campaign experience models."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tortoise import fields
from tortoise.validators import MinLengthValidator

from vapi.constants import UserRole
from vapi.db.sql_models.base import BaseModel
from vapi.db.sql_models.validators import validate_email_format

if TYPE_CHECKING:
    from vapi.db.sql_models.aws import S3Asset
    from vapi.db.sql_models.campaign import Campaign
    from vapi.db.sql_models.character import Character
    from vapi.db.sql_models.chargen_session import ChargenSession
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.diceroll import DiceRoll
    from vapi.db.sql_models.notes import Note
    from vapi.db.sql_models.quickroll import QuickRoll


class User(BaseModel):
    """A user of the application."""

    name_first = fields.CharField(max_length=50, null=True, validators=[MinLengthValidator(2)])
    name_last = fields.CharField(max_length=50, null=True, validators=[MinLengthValidator(2)])
    username = fields.CharField(max_length=50, validators=[MinLengthValidator(3)])
    email = fields.CharField(max_length=255, validators=[validate_email_format])
    role = fields.CharEnumField(UserRole)
    lifetime_xp = fields.IntField(default=0)
    lifetime_cool_points = fields.IntField(default=0)

    # OAuth profiles -opaque JSON blobs
    google_profile: Any = fields.JSONField(null=True)
    github_profile: Any = fields.JSONField(null=True)
    discord_profile: Any = fields.JSONField(null=True)
    discord_oauth: Any = fields.JSONField(null=True)

    # FK
    company: fields.ForeignKeyRelation[Company] = fields.ForeignKeyField(
        "models.Company", related_name="users", on_delete=fields.OnDelete.CASCADE
    )

    # Reverse relations
    campaign_experiences: fields.ReverseRelation[CampaignExperience]
    created_characters: fields.ReverseRelation[Character]
    played_characters: fields.ReverseRelation[Character]
    dice_rolls: fields.ReverseRelation[DiceRoll]
    quick_rolls: fields.ReverseRelation[QuickRoll]
    chargen_sessions: fields.ReverseRelation[ChargenSession]
    uploaded_assets: fields.ReverseRelation[S3Asset]
    owned_assets: fields.ReverseRelation[S3Asset]
    notes: fields.ReverseRelation[Note]

    class Meta:
        """Tortoise ORM meta options."""

        table = "user"


class CampaignExperience(BaseModel):
    """XP and cool point tracking for a user within a specific campaign."""

    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="campaign_experiences", on_delete=fields.OnDelete.CASCADE
    )
    campaign: fields.ForeignKeyRelation[Campaign] = fields.ForeignKeyField(
        "models.Campaign",
        related_name="user_experiences",
        on_delete=fields.OnDelete.CASCADE,
    )
    xp_current = fields.IntField(default=0)
    xp_total = fields.IntField(default=0)
    cool_points = fields.IntField(default=0)

    class Meta:
        """Tortoise ORM meta options."""

        table = "campaign_experience"
        unique_together = (("user", "campaign"),)
