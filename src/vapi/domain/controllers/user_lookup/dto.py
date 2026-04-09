"""User lookup DTOs."""

from uuid import UUID

import msgspec


class UserLookupResult(msgspec.Struct):
    """A single match from a cross-company user lookup."""

    company_id: UUID
    company_name: str
    user_id: UUID
    role: str
