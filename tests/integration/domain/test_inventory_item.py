"""Test inventory item."""

from collections.abc import Callable
from uuid import UUID

import pytest
from httpx import AsyncClient
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from vapi.constants import InventoryItemType
from vapi.db.sql_models.character import Character, CharacterInventory
from vapi.db.sql_models.company import Company
from vapi.domain.urls import Characters

pytestmark = pytest.mark.anyio


class TestInventoryItem:
    """Test inventory item controllers."""

    async def test_list_inventory_items(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        pg_mirror_company: Company,
        pg_mirror_global_admin,
        pg_character_factory: Callable[..., Character],
        pg_character_inventory_factory: Callable[..., CharacterInventory],
        token_global_admin: dict[str, str],
        neutralize_after_response_hook,
    ) -> None:
        """Verify listing inventory items returns only non-archived items."""
        # Given a character with one active and one archived inventory item
        character = await pg_character_factory(company=pg_mirror_company)
        item = await pg_character_inventory_factory(
            character=character, name="Test Item", type=InventoryItemType.OTHER
        )
        await pg_character_inventory_factory(
            character=character,
            name="Archived Item",
            type=InventoryItemType.OTHER,
            is_archived=True,
        )

        # When we list inventory items
        response = await client.get(
            build_url(
                Characters.INVENTORY,
                company_id=pg_mirror_company.id,
                user_id=character.user_player_id,
                campaign_id=character.campaign_id,
                character_id=character.id,
            ),
            headers=token_global_admin,
        )

        # Then we should get a 200 with only the non-archived item
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(item.id)
        assert data["items"][0]["name"] == "Test Item"
        assert data["items"][0]["type"] == "OTHER"
        assert data["items"][0]["character_id"] == str(character.id)
        assert data["items"][0]["description"] is None

    async def test_get_inventory_item(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        pg_mirror_company: Company,
        pg_mirror_global_admin,
        pg_character_factory: Callable[..., Character],
        pg_character_inventory_factory: Callable[..., CharacterInventory],
        token_global_admin: dict[str, str],
        neutralize_after_response_hook,
    ) -> None:
        """Verify retrieving a single inventory item by ID returns correct data."""
        # Given a character with an inventory item
        character = await pg_character_factory(company=pg_mirror_company)
        item = await pg_character_inventory_factory(
            character=character, name="Test Item", type=InventoryItemType.OTHER
        )

        # When we get the inventory item
        response = await client.get(
            build_url(
                Characters.INVENTORY_DETAIL,
                company_id=pg_mirror_company.id,
                user_id=character.user_player_id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                inventory_item_id=item.id,
            ),
            headers=token_global_admin,
        )

        # Then we should get a 200 with the item details
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["id"] == str(item.id)
        assert data["name"] == "Test Item"
        assert data["type"] == "OTHER"
        assert data["character_id"] == str(character.id)
        assert data["description"] is None

    async def test_get_inventory_item_not_found(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        pg_mirror_company: Company,
        pg_mirror_global_admin,
        pg_character_factory: Callable[..., Character],
        pg_character_inventory_factory: Callable[..., CharacterInventory],
        token_global_admin: dict[str, str],
        neutralize_after_response_hook,
    ) -> None:
        """Verify that requesting an archived inventory item returns 404."""
        # Given a character with an archived inventory item
        character = await pg_character_factory(company=pg_mirror_company)
        item = await pg_character_inventory_factory(
            character=character,
            name="Archived Item",
            type=InventoryItemType.OTHER,
            is_archived=True,
        )

        # When we request the archived item
        response = await client.get(
            build_url(
                Characters.INVENTORY_DETAIL,
                company_id=pg_mirror_company.id,
                user_id=character.user_player_id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                inventory_item_id=item.id,
            ),
            headers=token_global_admin,
        )

        # Then we should get a 404
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Inventory item not found"

    async def test_create_inventory_item(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        pg_mirror_company: Company,
        pg_mirror_global_admin,
        pg_character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        neutralize_after_response_hook,
    ) -> None:
        """Verify creating an inventory item persists it with the correct data."""
        # Given a character
        character = await pg_character_factory(company=pg_mirror_company)

        # When we create an inventory item
        response = await client.post(
            build_url(
                Characters.INVENTORY_CREATE,
                company_id=pg_mirror_company.id,
                user_id=character.user_player_id,
                campaign_id=character.campaign_id,
                character_id=character.id,
            ),
            headers=token_global_admin,
            json={
                "name": "Test Item",
                "type": "OTHER",
                "description": "Test Description",
            },
        )

        # Then we should get a 201 with the new item data
        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Test Item"
        assert data["type"] == "OTHER"
        assert data["description"] == "Test Description"
        assert data["character_id"] == str(character.id)
        assert data["id"] is not None
        assert data["date_created"] is not None
        assert data["date_modified"] is not None

        # And the item exists in the database
        db_item = await CharacterInventory.get(id=UUID(data["id"]))
        assert db_item.name == "Test Item"
        assert db_item.type == InventoryItemType.OTHER
        assert str(db_item.character_id) == str(character.id)

    async def test_create_inventory_item_invalid_data(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        pg_mirror_company: Company,
        pg_mirror_global_admin,
        pg_character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        neutralize_after_response_hook,
    ) -> None:
        """Verify creating an inventory item with an invalid type returns 400."""
        # Given a character
        character = await pg_character_factory(company=pg_mirror_company)

        # When we post invalid enum data
        response = await client.post(
            build_url(
                Characters.INVENTORY_CREATE,
                company_id=pg_mirror_company.id,
                user_id=character.user_player_id,
                campaign_id=character.campaign_id,
                character_id=character.id,
            ),
            headers=token_global_admin,
            json={
                "name": "Test Item",
                "type": "SOMETHING_INVALID",
            },
        )

        # Then we should get a 400 with an invalid_parameters error mentioning the bad value
        assert response.status_code == HTTP_400_BAD_REQUEST
        data = response.json()
        invalid = data.get("invalid_parameters", [])
        assert any("SOMETHING_INVALID" in p.get("message", "") for p in invalid)

    async def test_create_inventory_item_missing_data(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        pg_mirror_company: Company,
        pg_mirror_global_admin,
        pg_character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        neutralize_after_response_hook,
    ) -> None:
        """Verify creating an inventory item without required fields returns 400."""
        # Given a character
        character = await pg_character_factory(company=pg_mirror_company)

        # When we post an empty body
        response = await client.post(
            build_url(
                Characters.INVENTORY_CREATE,
                company_id=pg_mirror_company.id,
                user_id=character.user_player_id,
                campaign_id=character.campaign_id,
                character_id=character.id,
            ),
            headers=token_global_admin,
            json={},
        )

        # Then we should get a 400 with an invalid_parameters error about the missing name field
        assert response.status_code == HTTP_400_BAD_REQUEST
        data = response.json()
        invalid = data.get("invalid_parameters", [])
        assert any("name" in p.get("message", "") for p in invalid)

    async def test_update_inventory_item(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        pg_mirror_company: Company,
        pg_mirror_global_admin,
        pg_character_factory: Callable[..., Character],
        pg_character_inventory_factory: Callable[..., CharacterInventory],
        token_global_admin: dict[str, str],
        neutralize_after_response_hook,
    ) -> None:
        """Verify updating an inventory item persists the changed fields."""
        # Given a character with an inventory item
        character = await pg_character_factory(company=pg_mirror_company)
        item = await pg_character_inventory_factory(
            character=character,
            name="Test Item",
            type=InventoryItemType.OTHER,
            description="Test Description",
        )

        # When we patch the item description
        response = await client.patch(
            build_url(
                Characters.INVENTORY_UPDATE,
                company_id=pg_mirror_company.id,
                user_id=character.user_player_id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                inventory_item_id=item.id,
            ),
            headers=token_global_admin,
            json={"description": "Updated Description"},
        )

        # Then we should get a 200 with the updated item
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["name"] == "Test Item"
        assert data["description"] == "Updated Description"
        assert data["type"] == "OTHER"
        assert data["character_id"] == str(character.id)

        # And the database reflects the update
        await item.refresh_from_db()
        assert item.description == "Updated Description"
        assert item.name == "Test Item"
        assert item.type == InventoryItemType.OTHER

    async def test_delete_inventory_item(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        pg_mirror_company: Company,
        pg_mirror_global_admin,
        pg_character_factory: Callable[..., Character],
        pg_character_inventory_factory: Callable[..., CharacterInventory],
        token_global_admin: dict[str, str],
        neutralize_after_response_hook,
    ) -> None:
        """Verify deleting an inventory item archives it rather than removing it."""
        # Given a character with an inventory item
        character = await pg_character_factory(company=pg_mirror_company)
        item = await pg_character_inventory_factory(
            character=character, name="Test Item", type=InventoryItemType.OTHER
        )

        # When we delete the inventory item
        response = await client.delete(
            build_url(
                Characters.INVENTORY_DELETE,
                company_id=pg_mirror_company.id,
                user_id=character.user_player_id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                inventory_item_id=item.id,
            ),
            headers=token_global_admin,
        )

        # Then we should get a 204 and the item should be archived
        assert response.status_code == HTTP_204_NO_CONTENT
        await item.refresh_from_db()
        assert item.is_archived
