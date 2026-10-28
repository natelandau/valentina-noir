"""Developer DTOs."""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import msgspec

from vapi.constants import CompanyPermission
from vapi.domain.controllers.company.dto import CompanyPermissionResponse

if TYPE_CHECKING:
    from vapi.db.sql_models.developer import Developer


class DeveloperResponse(msgspec.Struct):
    """Response body for a developer."""

    id: UUID
    date_created: datetime
    date_modified: datetime
    username: str
    email: str
    key_generated: datetime | None
    provider_audiences: dict[str, list[str]] | None
    companies: list[CompanyPermissionResponse]

    @classmethod
    def from_model(cls, m: "Developer") -> "DeveloperResponse":
        """Convert a Tortoise Developer to a response Struct.

        Requires the permissions and their related company relations to be prefetched.
        """
        return cls(
            id=m.id,
            date_created=m.date_created,
            date_modified=m.date_modified,
            username=m.username,
            email=m.email,
            key_generated=m.key_generated,
            provider_audiences=m.provider_audiences,
            # A REVOKE row means no access, so it is not one of the developer's companies
            companies=[
                CompanyPermissionResponse.from_model(p)
                for p in m.permissions
                if p.permission != CompanyPermission.REVOKE
            ],
        )


class DeveloperPatch(msgspec.Struct):
    """Request body for partially updating a developer.

    All fields use UNSET as default to distinguish 'not sent' from 'sent as null'.
    """

    username: str | msgspec.UnsetType = msgspec.UNSET
    email: str | msgspec.UnsetType = msgspec.UNSET
    provider_audiences: Any | msgspec.UnsetType = msgspec.UNSET
