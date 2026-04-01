"""Company and company settings models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields

from vapi.constants import (
    PermissionManageCampaign,
    PermissionsFreeTraitChanges,
    PermissionsGrantXP,
)
from vapi.db.sql_models.base import BaseModel
from vapi.db.sql_models.validators import (
    validate_company_settings_num_choices,
    validate_company_settings_xp_cost,
)

if TYPE_CHECKING:
    from vapi.db.sql_models.aws import S3Asset
    from vapi.db.sql_models.campaign import Campaign
    from vapi.db.sql_models.character import Character
    from vapi.db.sql_models.character_concept import CharacterConcept
    from vapi.db.sql_models.chargen_session import ChargenSession
    from vapi.db.sql_models.developer import DeveloperCompanyPermission
    from vapi.db.sql_models.diceroll import DiceRoll
    from vapi.db.sql_models.dictionary import DictionaryTerm
    from vapi.db.sql_models.notes import Note
    from vapi.db.sql_models.user import User


class Company(BaseModel):
    """An organization that owns campaigns, characters, and users."""

    name = fields.CharField(max_length=50)
    description = fields.TextField(null=True)
    email = fields.CharField(max_length=255)
    resources_modified_at = fields.DatetimeField(null=True)

    # Reverse relations
    settings: fields.OneToOneRelation[CompanySettings]
    users: fields.ReverseRelation[User]
    character_concepts: fields.ReverseRelation[CharacterConcept]
    campaigns: fields.ReverseRelation[Campaign]
    characters: fields.ReverseRelation[Character]
    developer_permissions: fields.ReverseRelation[DeveloperCompanyPermission]
    dictionary_terms: fields.ReverseRelation[DictionaryTerm]
    dice_rolls: fields.ReverseRelation[DiceRoll]
    chargen_sessions: fields.ReverseRelation[ChargenSession]
    assets: fields.ReverseRelation[S3Asset]
    notes: fields.ReverseRelation[Note]

    class Meta:
        """Tortoise ORM meta options."""

        table = "company"


class CompanySettings(BaseModel):
    """Configuration settings for a company. One-to-one with Company."""

    company: fields.OneToOneRelation[Company] = fields.OneToOneField(
        "models.Company", related_name="settings", on_delete=fields.OnDelete.CASCADE
    )
    character_autogen_xp_cost = fields.IntField(
        default=10, validators=[validate_company_settings_xp_cost]
    )
    character_autogen_num_choices = fields.IntField(
        default=3, validators=[validate_company_settings_num_choices]
    )
    permission_manage_campaign = fields.CharEnumField(
        PermissionManageCampaign, default=PermissionManageCampaign.UNRESTRICTED
    )
    permission_grant_xp = fields.CharEnumField(
        PermissionsGrantXP, default=PermissionsGrantXP.UNRESTRICTED
    )
    permission_free_trait_changes = fields.CharEnumField(
        PermissionsFreeTraitChanges, default=PermissionsFreeTraitChanges.UNRESTRICTED
    )

    class Meta:
        """Tortoise ORM meta options."""

        table = "company_settings"
