"""Global admin DTOs."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import msgspec

from vapi.domain.controllers.company.dto import CompanyPermissionResponse

if TYPE_CHECKING:
    from vapi.db.sql_models.developer import Developer


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
            companies=[CompanyPermissionResponse.from_model(p) for p in m.permissions],
        )


class AdminDeveloperPatch(msgspec.Struct):
    """Request body for partially updating a developer as global admin."""

    username: str | msgspec.UnsetType = msgspec.UNSET
    email: str | msgspec.UnsetType = msgspec.UNSET
    is_global_admin: bool | msgspec.UnsetType = msgspec.UNSET
