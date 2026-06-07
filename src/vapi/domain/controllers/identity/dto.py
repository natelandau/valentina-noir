"""Identity resolution DTOs."""

import msgspec

from vapi.domain.controllers.user.dto import UserResponse
from vapi.domain.services.identity_svc import IdentityResolution


class IdentifyRequest(msgspec.Struct):
    """Request body for resolving a verified provider login to a user."""

    provider: str
    token: str
    username: str | None = None
    email: str | None = None


class LinkIdentityRequest(msgspec.Struct):
    """Request body for linking an additional provider identity to a user."""

    provider: str
    token: str


class IdentifyResponse(msgspec.Struct):
    """Response body for identity resolution."""

    resolution: IdentityResolution
    user: UserResponse
