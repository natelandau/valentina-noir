"""Chargen session model."""

from datetime import datetime
from typing import ClassVar

from beanie import Link, PydanticObjectId
from pymongo import IndexModel

from vapi.db.models.base import BaseDocument
from vapi.db.models.character import Character


class ChargenSession(BaseDocument):
    """Persist a character generation session for retrieval before expiration."""

    user_id: PydanticObjectId
    company_id: PydanticObjectId
    campaign_id: PydanticObjectId
    characters: list[Link[Character]]
    expires_at: datetime
    requires_selection: bool

    class Settings:
        """Settings for the ChargenSession model."""

        indexes: ClassVar[list[str | IndexModel]] = [
            IndexModel([("user_id", 1), ("company_id", 1), ("expires_at", 1)]),
            "campaign_id",
        ]
