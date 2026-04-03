"""Character inventory controllers."""

import asyncio
from typing import Annotated

import msgspec
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.sql_models.character import Character, CharacterInventory
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.lib.guards import (
    developer_company_user_guard,
    user_character_player_or_storyteller_guard,
    user_not_unapproved_guard,
)
from vapi.openapi.tags import APITags

from . import docs
from .dto import InventoryItemCreate, InventoryItemPatch, InventoryItemResponse


class CharacterInventoryController(Controller):
    """Character inventory controller."""

    tags = [APITags.CHARACTERS_INVENTORY.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "character": Provide(deps.provide_character_by_id_and_company),
        "inventory_item": Provide(deps.provide_inventory_item_by_id),
        "developer": Provide(deps.provide_developer_from_request),
    }
    guards = [developer_company_user_guard, user_not_unapproved_guard]

    @get(
        path=urls.Characters.INVENTORY,
        summary="List inventory items",
        operation_id="listCharacterInventoryItems",
        description=docs.LIST_INVENTORY_ITEMS_DESCRIPTION,
        cache=True,
    )
    async def list_inventory_items(
        self,
        character: Character,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[InventoryItemResponse]:
        """List all inventory items."""
        qs = CharacterInventory.filter(character_id=character.id, is_archived=False)
        count, items = await asyncio.gather(
            qs.count(),
            qs.offset(offset).limit(limit),
        )
        return OffsetPagination(
            items=[InventoryItemResponse.from_model(i) for i in items],
            limit=limit,
            offset=offset,
            total=count,
        )

    @get(
        path=urls.Characters.INVENTORY_DETAIL,
        summary="Get inventory item",
        operation_id="getCharacterInventoryItem",
        description=docs.GET_INVENTORY_ITEM_DESCRIPTION,
        cache=True,
    )
    async def get_inventory_item(
        self, *, inventory_item: CharacterInventory
    ) -> InventoryItemResponse:
        """Get an inventory item by ID."""
        return InventoryItemResponse.from_model(inventory_item)

    @post(
        path=urls.Characters.INVENTORY_CREATE,
        summary="Create inventory item",
        operation_id="createCharacterInventoryItem",
        description=docs.CREATE_INVENTORY_ITEM_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
        guards=[user_character_player_or_storyteller_guard],
    )
    async def create_inventory_item(
        self, *, character: Character, data: InventoryItemCreate
    ) -> InventoryItemResponse:
        """Create an inventory item."""
        item = await CharacterInventory.create(
            character=character,
            name=data.name,
            description=data.description,
            type=data.type,
        )
        return InventoryItemResponse.from_model(item)

    @patch(
        path=urls.Characters.INVENTORY_UPDATE,
        summary="Update inventory item",
        operation_id="updateCharacterInventoryItem",
        description=docs.UPDATE_INVENTORY_ITEM_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
        guards=[user_character_player_or_storyteller_guard],
    )
    async def update_inventory_item(
        self,
        *,
        inventory_item: CharacterInventory,
        data: InventoryItemPatch,
    ) -> InventoryItemResponse:
        """Update an inventory item."""
        for field_name in ("name", "description", "type"):
            value = getattr(data, field_name)
            if not isinstance(value, msgspec.UnsetType):
                setattr(inventory_item, field_name, value)
        await inventory_item.save()
        return InventoryItemResponse.from_model(inventory_item)

    @delete(
        path=urls.Characters.INVENTORY_DELETE,
        summary="Delete inventory item",
        operation_id="deleteCharacterInventoryItem",
        description=docs.DELETE_INVENTORY_ITEM_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
        guards=[user_character_player_or_storyteller_guard],
    )
    async def delete_inventory_item(self, *, inventory_item: CharacterInventory) -> None:
        """Delete an inventory item."""
        inventory_item.is_archived = True
        await inventory_item.save()
