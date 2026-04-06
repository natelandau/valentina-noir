"""Character inventory DTOs — msgspec Structs for request/response bodies."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import msgspec

from vapi.constants import InventoryItemType

if TYPE_CHECKING:
    from vapi.db.sql_models.character import CharacterInventory


class InventoryItemResponse(msgspec.Struct):
    """Response body for an inventory item."""

    id: UUID
    name: str
    description: str | None
    type: InventoryItemType
    character_id: UUID
    date_created: datetime
    date_modified: datetime
    is_archived: bool

    @classmethod
    def from_model(cls, m: "CharacterInventory") -> "InventoryItemResponse":
        """Convert a Tortoise CharacterInventory to a response Struct."""
        return cls(
            id=m.id,
            name=m.name,
            description=m.description,
            type=m.type,
            character_id=m.character_id,  # type: ignore[attr-defined]
            date_created=m.date_created,
            date_modified=m.date_modified,
            is_archived=m.is_archived,
        )


class InventoryItemCreate(msgspec.Struct):
    """Request body for creating an inventory item."""

    name: str
    type: InventoryItemType
    description: str | None = None


class InventoryItemPatch(msgspec.Struct):
    """Request body for partially updating an inventory item."""

    name: str | msgspec.UnsetType = msgspec.UNSET
    description: str | None | msgspec.UnsetType = msgspec.UNSET
    type: InventoryItemType | msgspec.UnsetType = msgspec.UNSET
