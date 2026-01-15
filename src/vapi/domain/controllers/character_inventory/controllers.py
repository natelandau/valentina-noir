"""Character inventory controllers."""

from __future__ import annotations

from typing import Annotated

from litestar.controller import Controller
from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter
from pydantic import ValidationError as PydanticValidationError

from vapi.db.models import Character, CharacterInventory
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags
from vapi.utils.validation import raise_from_pydantic_validation_error

from . import dto

# TODO: Add guards for player ownership or storyteller for patches and deletions.


class CharacterInventoryController(Controller):
    """Character inventory controller."""

    tags = [APITags.CHARACTERS_INVENTORY.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "character": Provide(deps.provide_character_by_id_and_company),
        "inventory_item": Provide(deps.provide_inventory_item_by_id),
    }
    guards = [developer_company_user_guard]
    return_dto = dto.ReturnDTO

    @get(
        path=urls.Characters.INVENTORY,
        summary="List inventory items",
        operation_id="listCharacterInventoryItems",
        description="Retrieve a paginated list of items in a character's inventory. Items can be equipment, consumables, or other possessions.",
        cache=True,
    )
    async def list_inventory_items(
        self,
        character: Character,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[CharacterInventory]:
        """List all inventory items."""
        query = {
            "character_id": character.id,
            "is_archived": False,
        }
        count = await CharacterInventory.find(query).count()
        inventory_items = await CharacterInventory.find(query).skip(offset).limit(limit).to_list()
        return OffsetPagination(items=inventory_items, limit=limit, offset=offset, total=count)

    @get(
        path=urls.Characters.INVENTORY_DETAIL,
        summary="Get inventory item",
        operation_id="getCharacterInventoryItem",
        description="Retrieve detailed information about a specific inventory item.",
        cache=True,
    )
    async def get_inventory_item(self, *, inventory_item: CharacterInventory) -> CharacterInventory:
        """Get an inventory item by ID."""
        return inventory_item

    @post(
        path=urls.Characters.INVENTORY_CREATE,
        summary="Create inventory item",
        operation_id="createCharacterInventoryItem",
        description="Add a new item to a character's inventory. Specify the item type, name, description, and any mechanical properties.",
        dto=dto.PostDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def create_inventory_item(
        self, *, character: Character, data: DTOData[CharacterInventory]
    ) -> CharacterInventory:
        """Update an inventory item by ID."""
        item_data = data.create_instance(character_id=character.id)
        item = CharacterInventory(
            **item_data.model_dump(exclude_unset=True),
        )
        await item.save()
        return item

    @patch(
        path=urls.Characters.INVENTORY_UPDATE,
        summary="Update inventory item",
        operation_id="updateCharacterInventoryItem",
        description="Modify an inventory item's properties. Only include fields that need to be changed.",
        dto=dto.PatchDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def update_inventory_item(
        self,
        *,
        inventory_item: CharacterInventory,
        data: DTOData[CharacterInventory],
    ) -> CharacterInventory:
        """Update an inventory item by ID."""
        updated_item = data.update_instance(inventory_item)
        try:
            await updated_item.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return updated_item

    @delete(
        path=urls.Characters.INVENTORY_DELETE,
        summary="Delete inventory item",
        operation_id="deleteCharacterInventoryItem",
        description="Remove an item from a character's inventory. This action cannot be undone.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def delete_inventory_item(self, *, inventory_item: CharacterInventory) -> None:
        """Delete an inventory item by ID."""
        inventory_item.is_archived = True
        await inventory_item.save()
