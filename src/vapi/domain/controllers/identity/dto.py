"""Identity resolution DTOs."""

from typing import Annotated

import msgspec

from vapi.constants import IdentityProvider
from vapi.domain.controllers.request_types import NameMax50
from vapi.domain.controllers.user.dto import UserResponse
from vapi.domain.services.identity_svc import IdentityResolution

# The service treats an empty username or email as absent, so username (NameMax50) and email
# carry only the model's maximum length, not its minimum or email pattern.
OptionalEmail = Annotated[str, msgspec.Meta(max_length=255)]


class IdentifyRequest(msgspec.Struct):
    """Request body for resolving a verified provider login to a user."""

    provider: IdentityProvider
    token: str
    username: NameMax50 | None = None
    email: OptionalEmail | None = None


class LinkIdentityRequest(msgspec.Struct):
    """Request body for linking an additional provider identity to a user."""

    provider: IdentityProvider
    token: str


class IdentifyResponse(msgspec.Struct):
    """Response body for identity resolution."""

    resolution: IdentityResolution
    user: UserResponse
