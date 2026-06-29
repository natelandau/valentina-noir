"""Global admin DTOs."""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import msgspec

from vapi.domain.controllers.company.dto import CompanyPermissionResponse
from vapi.domain.controllers.user.dto import UserResponse

if TYPE_CHECKING:
    from vapi.db.sql_models.developer import Developer
    from vapi.db.sql_models.user import User


class DeveloperCreate(msgspec.Struct):
    """Request body for creating a developer."""

    username: str
    email: str
    is_global_admin: bool = False


class DeveloperAdminResponse(msgspec.Struct):
    """Response body for a developer in the global admin context.

    Includes is_global_admin which the regular DeveloperResponse omits.
    """

    id: UUID
    date_created: datetime
    date_modified: datetime
    username: str
    email: str
    is_global_admin: bool
    key_generated: datetime | None
    provider_audiences: dict[str, list[str]] | None
    companies: list[CompanyPermissionResponse]

    @classmethod
    def from_model(cls, m: "Developer") -> "DeveloperAdminResponse":
        """Convert a Tortoise Developer to an admin response Struct.

        Requires the permissions and their related company relations to be prefetched.
        """
        return cls(
            id=m.id,
            date_created=m.date_created,
            date_modified=m.date_modified,
            username=m.username,
            email=m.email,
            is_global_admin=m.is_global_admin,
            key_generated=m.key_generated,
            provider_audiences=m.provider_audiences,
            companies=[CompanyPermissionResponse.from_model(p) for p in m.permissions],
        )


class AdminDeveloperPatch(msgspec.Struct):
    """Request body for partially updating a developer as global admin."""

    username: str | msgspec.UnsetType = msgspec.UNSET
    email: str | msgspec.UnsetType = msgspec.UNSET
    is_global_admin: bool | msgspec.UnsetType = msgspec.UNSET
    provider_audiences: Any | msgspec.UnsetType = msgspec.UNSET


class AdminUserCreate(msgspec.Struct):
    """Request body for creating a user as a global admin.

    The global admin domain has no ambient company, so the target company is
    carried in the body via ``company_id`` rather than the URL path.
    """

    company_id: UUID
    username: str
    email: str
    role: str
    name_first: str | None = None
    name_last: str | None = None


class AdminUserPatch(msgspec.Struct):
    """Request body for updating a user as a global admin.

    Setting ``is_archived`` to ``false`` restores a soft-deleted user, reversing the
    archive cascade so the data archived with them is restored too. Restoring is
    refused while the user's company is archived.
    """

    name_first: str | None | msgspec.UnsetType = msgspec.UNSET
    name_last: str | None | msgspec.UnsetType = msgspec.UNSET
    username: str | msgspec.UnsetType = msgspec.UNSET
    email: str | msgspec.UnsetType = msgspec.UNSET
    role: str | msgspec.UnsetType = msgspec.UNSET
    is_archived: bool | msgspec.UnsetType = msgspec.UNSET


class AdminUserResponse(UserResponse):
    """User response for the global admin domain.

    Subclasses the tenant ``UserResponse`` so upstream field changes are picked
    up automatically, and adds ``is_archived``, which the tenant response omits
    because archived state is only surfaced inside the global admin domain.
    """

    is_archived: bool

    @classmethod
    def from_model(cls, m: "User") -> "AdminUserResponse":
        """Convert a User to an admin response including archived state.

        Requires ``campaign_experiences`` to be prefetched (same as UserResponse).

        Args:
            m: The user to serialize.

        Returns:
            The admin response with every UserResponse field plus is_archived.
        """
        base = UserResponse.from_model(m)
        # Exclude is_archived so this stays correct (no duplicate keyword) if the
        # tenant UserResponse ever gains an is_archived field of its own.
        fields = {f: getattr(base, f) for f in base.__struct_fields__ if f != "is_archived"}
        return cls(**fields, is_archived=m.is_archived)
