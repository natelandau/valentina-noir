"""Company DTOs."""

from datetime import datetime
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

import msgspec

from vapi.constants import (
    CompanyPermission,
    PermissionManageCampaign,
    PermissionManageNPC,
    PermissionsFreeTraitChanges,
    PermissionsGrantXP,
    PermissionsRecoupXP,
)
from vapi.db.sql_models.validators import (
    NUM_CHOICES_MAX,
    NUM_CHOICES_MIN,
    STARTING_POINTS_MAX,
    STARTING_POINTS_MIN,
    XP_COST_MAX,
    XP_COST_MIN,
)
from vapi.domain.controllers.request_types import Email, Name3to50

if TYPE_CHECKING:
    from vapi.db.sql_models.company import Company, CompanySettings
    from vapi.db.sql_models.developer import DeveloperCompanyPermission
    from vapi.db.sql_models.user import User


class CompanySettingsResponse(msgspec.Struct):
    """Response body for company settings."""

    id: UUID
    character_autogen_xp_cost: int
    character_autogen_num_choices: int
    character_autogen_starting_points: int
    permission_manage_campaign: str
    permission_manage_npc: str
    permission_grant_xp: str
    permission_free_trait_changes: str
    permission_recoup_xp: str
    specialty_xp_cost_enabled: bool

    @classmethod
    def from_model(cls, m: "CompanySettings") -> "CompanySettingsResponse":
        """Convert a Tortoise CompanySettings to a response Struct."""
        return cls(
            id=m.id,
            character_autogen_xp_cost=m.character_autogen_xp_cost,
            character_autogen_num_choices=m.character_autogen_num_choices,
            character_autogen_starting_points=m.character_autogen_starting_points,
            permission_manage_campaign=m.permission_manage_campaign.value,
            permission_manage_npc=m.permission_manage_npc.value,
            permission_grant_xp=m.permission_grant_xp.value,
            permission_free_trait_changes=m.permission_free_trait_changes.value,
            permission_recoup_xp=m.permission_recoup_xp.value,
            specialty_xp_cost_enabled=m.specialty_xp_cost_enabled,
        )


class CompanyResponse(msgspec.Struct):
    """Response body for a company."""

    id: UUID
    date_created: datetime
    date_modified: datetime
    name: str
    description: str | None
    email: str
    resources_modified_at: datetime
    num_campaigns: int
    num_player_characters: int
    num_storyteller_characters: int
    num_npc_characters: int
    num_users: int
    settings: CompanySettingsResponse

    @classmethod
    def from_model(cls, m: "Company") -> "CompanyResponse":
        """Convert a Tortoise Company to a response Struct.

        Requires the `settings` relation to be prefetched and count annotations
        to be present on the model instance before calling.
        """
        return cls(
            id=m.id,
            date_created=m.date_created,
            date_modified=m.date_modified,
            name=m.name,
            description=m.description,
            email=m.email,
            resources_modified_at=m.resources_modified_at,
            num_campaigns=m.num_campaigns,  # ty:ignore[unresolved-attribute]
            num_player_characters=m.num_player_characters,  # ty:ignore[unresolved-attribute]
            num_storyteller_characters=m.num_storyteller_characters,  # ty:ignore[unresolved-attribute]
            num_npc_characters=m.num_npc_characters,  # ty:ignore[unresolved-attribute]
            num_users=m.num_users,  # ty:ignore[unresolved-attribute]
            settings=CompanySettingsResponse.from_model(m.settings),
        )


class CompanyPermissionResponse(msgspec.Struct):
    """Response body for a developer's permission within a company."""

    company_id: UUID
    name: str
    permission: str

    @classmethod
    def from_model(cls, m: "DeveloperCompanyPermission") -> "CompanyPermissionResponse":
        """Convert a Tortoise DeveloperCompanyPermission to a response Struct.

        Requires the company relation to be prefetched before calling.
        """
        return cls(
            company_id=m.company.id,
            name=m.company.name,
            permission=m.permission.value,
        )


class UserResponse(msgspec.Struct):
    """Minimal response body for a user, used in new company creation responses."""

    id: UUID
    date_created: datetime
    date_modified: datetime
    username: str
    email: str
    role: str
    company_id: UUID

    @classmethod
    def from_model(cls, m: "User") -> "UserResponse":
        """Convert a Tortoise User to a response Struct."""
        return cls(
            id=m.id,
            date_created=m.date_created,
            date_modified=m.date_modified,
            username=m.username,
            email=m.email,
            role=m.role.value,
            company_id=m.company_id,  # ty:ignore[unresolved-attribute]
        )


class NewCompanyCreateResponse(msgspec.Struct):
    """Response body returned after creating a new company with an admin user."""

    company: CompanyResponse
    admin_user: UserResponse


Description3 = Annotated[str, msgspec.Meta(min_length=3)]
XpCost = Annotated[int, msgspec.Meta(ge=XP_COST_MIN, le=XP_COST_MAX)]
NumChoices = Annotated[int, msgspec.Meta(ge=NUM_CHOICES_MIN, le=NUM_CHOICES_MAX)]
StartingPoints = Annotated[int, msgspec.Meta(ge=STARTING_POINTS_MIN, le=STARTING_POINTS_MAX)]


class CompanySettingsCreate(msgspec.Struct):
    """Request body for creating company settings."""

    character_autogen_xp_cost: XpCost = 10
    character_autogen_num_choices: NumChoices = 3
    character_autogen_starting_points: StartingPoints = 0
    permission_manage_campaign: PermissionManageCampaign = PermissionManageCampaign.UNRESTRICTED
    permission_manage_npc: PermissionManageNPC = PermissionManageNPC.UNRESTRICTED
    permission_grant_xp: PermissionsGrantXP = PermissionsGrantXP.UNRESTRICTED
    permission_free_trait_changes: PermissionsFreeTraitChanges = (
        PermissionsFreeTraitChanges.UNRESTRICTED
    )
    permission_recoup_xp: PermissionsRecoupXP = PermissionsRecoupXP.DENIED
    specialty_xp_cost_enabled: bool = False


class CompanyCreate(msgspec.Struct):
    """Request body for creating a company."""

    name: Name3to50
    email: Email
    description: Description3 | None = None
    settings: CompanySettingsCreate | None = None


class CompanySettingsPatch(msgspec.Struct):
    """Request body for partially updating company settings.

    All fields use UNSET as default to distinguish 'not sent' from 'sent as null'.
    """

    character_autogen_xp_cost: XpCost | msgspec.UnsetType = msgspec.UNSET
    character_autogen_num_choices: NumChoices | msgspec.UnsetType = msgspec.UNSET
    character_autogen_starting_points: StartingPoints | msgspec.UnsetType = msgspec.UNSET
    permission_manage_campaign: PermissionManageCampaign | msgspec.UnsetType = msgspec.UNSET
    permission_manage_npc: PermissionManageNPC | msgspec.UnsetType = msgspec.UNSET
    permission_grant_xp: PermissionsGrantXP | msgspec.UnsetType = msgspec.UNSET
    permission_free_trait_changes: PermissionsFreeTraitChanges | msgspec.UnsetType = msgspec.UNSET
    permission_recoup_xp: PermissionsRecoupXP | msgspec.UnsetType = msgspec.UNSET
    specialty_xp_cost_enabled: bool | msgspec.UnsetType = msgspec.UNSET


class CompanyPatch(msgspec.Struct):
    """Request body for partially updating a company.

    All fields use UNSET as default to distinguish 'not sent' from 'sent as null'.
    """

    name: Name3to50 | msgspec.UnsetType = msgspec.UNSET
    description: Description3 | msgspec.UnsetType | None = msgspec.UNSET
    email: Email | msgspec.UnsetType = msgspec.UNSET
    settings: CompanySettingsPatch | msgspec.UnsetType = msgspec.UNSET


class CompanyPermissionRequest(msgspec.Struct):
    """Request body for setting a developer's permission within a company."""

    developer_id: UUID
    permission: CompanyPermission
