"""Company DTOs."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import msgspec
from tortoise.exceptions import NoValuesFetched

from vapi.constants import CompanyPermission

if TYPE_CHECKING:
    from vapi.db.sql_models.company import Company, CompanySettings
    from vapi.db.sql_models.developer import DeveloperCompanyPermission
    from vapi.db.sql_models.user import User


class CompanySettingsResponse(msgspec.Struct):
    """Response body for company settings."""

    id: UUID
    character_autogen_xp_cost: int
    character_autogen_num_choices: int
    permission_manage_campaign: str
    permission_grant_xp: str
    permission_free_trait_changes: str

    @classmethod
    def from_model(cls, m: "CompanySettings") -> "CompanySettingsResponse":
        """Convert a Tortoise CompanySettings to a response Struct."""
        return cls(
            id=m.id,
            character_autogen_xp_cost=m.character_autogen_xp_cost,
            character_autogen_num_choices=m.character_autogen_num_choices,
            permission_manage_campaign=m.permission_manage_campaign.value,
            permission_grant_xp=m.permission_grant_xp.value,
            permission_free_trait_changes=m.permission_free_trait_changes.value,
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
    settings: CompanySettingsResponse | None

    @classmethod
    def from_model(cls, m: "Company") -> "CompanyResponse":
        """Convert a Tortoise Company to a response Struct.

        Attempts to include settings if they have been prefetched; falls back to None
        when settings are not loaded to avoid triggering additional queries.
        """
        try:
            settings = CompanySettingsResponse.from_model(m.settings)
        except (AttributeError, NoValuesFetched):
            settings = None

        return cls(
            id=m.id,
            date_created=m.date_created,
            date_modified=m.date_modified,
            name=m.name,
            description=m.description,
            email=m.email,
            resources_modified_at=m.resources_modified_at,
            settings=settings,
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
            company_id=m.company_id,  # type: ignore[attr-defined]
        )


class NewCompanyCreateResponse(msgspec.Struct):
    """Response body returned after creating a new company with an admin user."""

    company: CompanyResponse
    admin_user: UserResponse


class CompanySettingsCreate(msgspec.Struct):
    """Request body for creating company settings."""

    character_autogen_xp_cost: int = 10
    character_autogen_num_choices: int = 3
    permission_manage_campaign: str = "UNRESTRICTED"
    permission_grant_xp: str = "UNRESTRICTED"
    permission_free_trait_changes: str = "UNRESTRICTED"


class CompanyCreate(msgspec.Struct):
    """Request body for creating a company."""

    name: str
    description: str | None = None
    email: str = ""
    settings: CompanySettingsCreate | None = None


class CompanySettingsPatch(msgspec.Struct):
    """Request body for partially updating company settings.

    All fields use UNSET as default to distinguish 'not sent' from 'sent as null'.
    """

    character_autogen_xp_cost: int | msgspec.UnsetType = msgspec.UNSET
    character_autogen_num_choices: int | msgspec.UnsetType = msgspec.UNSET
    permission_manage_campaign: str | msgspec.UnsetType = msgspec.UNSET
    permission_grant_xp: str | msgspec.UnsetType = msgspec.UNSET
    permission_free_trait_changes: str | msgspec.UnsetType = msgspec.UNSET


class CompanyPatch(msgspec.Struct):
    """Request body for partially updating a company.

    All fields use UNSET as default to distinguish 'not sent' from 'sent as null'.
    """

    name: str | msgspec.UnsetType = msgspec.UNSET
    description: str | None | msgspec.UnsetType = msgspec.UNSET
    email: str | msgspec.UnsetType = msgspec.UNSET
    settings: CompanySettingsPatch | msgspec.UnsetType = msgspec.UNSET


class CompanyPermissionRequest(msgspec.Struct):
    """Request body for setting a developer's permission within a company."""

    developer_id: UUID
    permission: CompanyPermission
