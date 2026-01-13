"""Company model."""

from typing import Annotated

from beanie import PydanticObjectId
from pydantic import EmailStr, Field

from vapi.constants import (
    DEFAULT_CHARACTER_AUTGEN_NUM_CHOICES,
    DEFAULT_CHARACTER_AUTGEN_XP_COST,
    PermissionManageCampaign,
    PermissionsGrantXP,
    PermissionsManageTraits,
)

from .base import BaseDocument, HashedBaseModel


class CompanySettings(HashedBaseModel):
    """Company settings model."""

    # Character Autogen
    character_autogen_xp_cost: Annotated[
        int | None,
        Field(ge=0, le=100, default=1, description="The cost to autogen an XP for a character."),
    ] = DEFAULT_CHARACTER_AUTGEN_XP_COST
    character_autogen_num_choices: Annotated[
        int | None,
        Field(
            ge=1,
            le=10,
            default=1,
            description="The number of character generated for a user to select from.",
        ),
    ] = DEFAULT_CHARACTER_AUTGEN_NUM_CHOICES

    # Permissions
    permission_manage_campaign: PermissionManageCampaign = Field(
        default=PermissionManageCampaign.UNRESTRICTED
    )
    permission_grant_xp: PermissionsGrantXP = Field(default=PermissionsGrantXP.UNRESTRICTED)
    permission_manage_traits: PermissionsManageTraits = Field(
        default=PermissionsManageTraits.UNRESTRICTED
    )


class Company(BaseDocument):
    """Company model."""

    name: Annotated[str, Field(min_length=3, max_length=50)]
    description: Annotated[str | None, Field(min_length=3, default=None)]
    email: EmailStr
    user_ids: list[PydanticObjectId] = Field(default_factory=list)
    settings: CompanySettings = Field(default=CompanySettings())
