"""Schemas for the CLI."""

from dataclasses import dataclass

from beanie import PydanticObjectId

__all__ = ("APIKeyUser",)


@dataclass
class APIKeyUser:
    """API key return."""

    api_key: str
    developer_id: PydanticObjectId
    developer_name: str
    developer_email: str
    developer_is_global_admin: bool
