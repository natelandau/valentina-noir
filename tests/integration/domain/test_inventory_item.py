"""Test inventory item."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from vapi.constants import InventoryItemType
from vapi.db.models import CharacterInventory
from vapi.domain.urls import Characters

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.models import Character

pytestmark = pytest.mark.anyio


class TestInventoryItem:
    """Test inventory item controllers."""

    async def test_list_inventory_items(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        base_character: Character,
        token_company_admin: dict[str, str],
    ) -> None:
        """Verify we can list inventory items."""
        item = CharacterInventory(
            character_id=base_character.id, name="Test Item", type=InventoryItemType.OTHER
        )
        await item.save()
        item2 = CharacterInventory(
            character_id=base_character.id,
            name="Test Item",
            type=InventoryItemType.OTHER,
            is_archived=True,
        )
        await item2.save()
        response = await client.get(build_url(Characters.INVENTORY), headers=token_company_admin)
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "items": [
                {
                    "character_id": str(base_character.id),
                    "date_created": item.date_created.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "date_modified": item.date_modified.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "id": str(item.id),
                    "name": "Test Item",
                    "description": None,
                    "type": "OTHER",
                },
            ],
            "limit": 10,
            "offset": 0,
            "total": 1,
        }

    async def test_get_inventory_item(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        base_character: Character,
        token_company_admin: dict[str, str],
    ) -> None:
        """Verify we can get an inventory item."""
        item = CharacterInventory(
            character_id=base_character.id, name="Test Item", type=InventoryItemType.OTHER
        )
        await item.save()
        response = await client.get(
            build_url(Characters.INVENTORY_DETAIL, inventory_item_id=item.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "character_id": str(base_character.id),
            "date_created": item.date_created.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date_modified": item.date_modified.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "id": str(item.id),
            "name": "Test Item",
            "description": None,
            "type": "OTHER",
        }

    async def test_get_inventory_item_not_found(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        base_character: Character,
        token_company_admin: dict[str, str],
    ) -> None:
        """Verify we get a 404 when getting an inventory item that doesn't exist."""
        item = CharacterInventory(
            character_id=base_character.id,
            name="Test Item",
            type=InventoryItemType.OTHER,
            is_archived=True,
        )
        await item.save()
        response = await client.get(
            build_url(Characters.INVENTORY_DETAIL, inventory_item_id=item.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Inventory item not found"

    async def test_create_inventory_item(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        base_character: Character,
        token_company_admin: dict[str, str],
    ) -> None:
        """Verify we can create an inventory item."""
        response = await client.post(
            build_url(Characters.INVENTORY_CREATE),
            headers=token_company_admin,
            json={
                "name": "Test Item",
                "type": "OTHER",
                "description": "Test Description",
            },
        )
        assert response.status_code == HTTP_201_CREATED
        assert response.json() == {
            "character_id": str(base_character.id),
            "date_created": response.json()["date_created"],
            "date_modified": response.json()["date_modified"],
            "id": response.json()["id"],
            "name": "Test Item",
            "description": "Test Description",
            "type": "OTHER",
        }
        db_item = await CharacterInventory.get(response.json()["id"])
        assert db_item.name == "Test Item"
        assert db_item.type == InventoryItemType.OTHER
        assert db_item.character_id == base_character.id

    async def test_create_inventory_item_invalid_data(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        base_character: Character,
        token_company_admin: dict[str, str],
    ) -> None:
        """Verify we can create an inventory item."""
        response = await client.post(
            build_url(Characters.INVENTORY_CREATE),
            headers=token_company_admin,
            json={
                "name": "Test Item",
                "type": "SOMETHING_INVALID",
            },
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Invalid enum value 'SOMETHING_INVALID' - at `$.type`"

    async def test_create_inventory_item_missing_data(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
    ) -> None:
        """Verify we can create an inventory item."""
        response = await client.post(
            build_url(Characters.INVENTORY_CREATE),
            headers=token_company_admin,
            json={},
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Object missing required field `name`"

    async def test_update_inventory_item(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        base_character: Character,
        token_company_admin: dict[str, str],
    ) -> None:
        """Verify we can update an inventory item."""
        item = CharacterInventory(
            character_id=base_character.id,
            name="Test Item",
            type=InventoryItemType.OTHER,
            description="Test Description",
        )
        await item.save()
        response = await client.patch(
            build_url(Characters.INVENTORY_UPDATE, inventory_item_id=item.id),
            headers=token_company_admin,
            json={
                "description": "Updated Description",
            },
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "character_id": str(base_character.id),
            "date_created": response.json()["date_created"],
            "date_modified": response.json()["date_modified"],
            "id": response.json()["id"],
            "name": "Test Item",
            "description": "Updated Description",
            "type": "OTHER",
        }
        db_item = await CharacterInventory.get(response.json()["id"])
        assert db_item.name == "Test Item"
        assert db_item.type == InventoryItemType.OTHER
        assert db_item.character_id == base_character.id
        assert db_item.description == "Updated Description"

    async def test_delete_inventory_item(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        base_character: Character,
        token_company_admin: dict[str, str],
    ) -> None:
        """Verify we can delete an inventory item."""
        item = CharacterInventory(
            character_id=base_character.id, name="Test Item", type=InventoryItemType.OTHER
        )
        await item.save()
        response = await client.delete(
            build_url(Characters.INVENTORY_DELETE, inventory_item_id=item.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_204_NO_CONTENT
        db_item = await CharacterInventory.get(item.id)
        assert db_item.is_archived
        assert db_item.archive_date is not None
