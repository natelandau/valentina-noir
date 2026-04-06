"""Schemas for the CLI."""

from dataclasses import dataclass, field
from uuid import UUID

__all__ = ("APIKeyUser",)


@dataclass
class APIKeyUser:
    """API key return."""

    api_key: str
    developer_id: UUID
    developer_name: str
    developer_email: str
    developer_is_global_admin: bool
    company_ids: list[UUID] = field(default_factory=list)
