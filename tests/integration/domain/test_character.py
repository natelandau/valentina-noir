"""Test character (Tortoise ORM)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from vapi.constants import CharacterClass, CharacterStatus, CharacterType
from vapi.db.sql_models.character import (
    Character,
    CharacterTrait,
    VampireAttributes,
    WerewolfAttributes,
)
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_sheet import CharSheetSection, Trait, TraitCategory
from vapi.domain.urls import Characters as CharacterURL

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.campaign import Campaign
    from vapi.db.sql_models.character_concept import CharacterConcept
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.developer import Developer
    from vapi.db.sql_models.user import User

pytestmark = pytest.mark.anyio


def _assert_character_response_shape(data: dict) -> None:
    """Assert that a character response has the expected top-level keys."""
    for key in (
        "id",
        "name_first",
        "name_last",
        "name",
        "name_full",
        "character_class",
        "type",
        "game_version",
        "status",
        "company_id",
        "campaign_id",
        "user_creator_id",
        "user_player_id",
        "date_created",
        "date_modified",
    ):
        assert key in data, f"Missing key '{key}' in character response"


class TestCharacterList:
    """Test character list endpoints."""

    async def test_list_characters_no_results(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify listing characters returns empty when none exist."""
        # When we list characters
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=session_company.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            params={"campaign_id": str(session_campaign.id)},
        )

        # Then we get an empty list
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == []

    async def test_list_characters_with_results_no_filters(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify listing characters returns all non-archived, non-temporary characters."""
        # Given multiple characters with various statuses/types
        second_user = await user_factory(company=session_company)
        character1 = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        character_dead = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            status=CharacterStatus.DEAD,
        )
        character_storyteller = await character_factory(
            company=session_company,
            user_creator=session_user,
            user_player=session_user,
            campaign=session_campaign,
            type=CharacterType.STORYTELLER,
        )
        character_different_user = await character_factory(
            company=session_company,
            user_creator=session_user,
            user_player=second_user,
            campaign=session_campaign,
        )
        # Different campaign — should not appear
        await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
        )
        # Archived — should not appear
        await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            is_archived=True,
        )
        # Temporary — should not appear (default filter is is_temporary=False)
        await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            is_temporary=True,
        )

        # When we list characters
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=session_company.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            params={"campaign_id": str(session_campaign.id)},
        )

        # Then we get the four non-archived, non-temporary characters
        assert response.status_code == HTTP_200_OK
        items = response.json()["items"]
        returned_ids = {item["id"] for item in items}
        assert returned_ids == {
            str(character1.id),
            str(character_dead.id),
            str(character_storyteller.id),
            str(character_different_user.id),
        }

    async def test_list_characters_with_results_specify_user_player_id(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify filtering by user_player_id returns only that user's characters."""
        # Given characters owned by different users
        second_user = await user_factory(company=session_company)
        await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        character_different_user = await character_factory(
            company=session_company,
            user_player=second_user,
            user_creator=session_user,
            campaign=session_campaign,
        )

        # When we filter by user_player_id
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=session_company.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            params={"campaign_id": str(session_campaign.id), "user_player_id": str(second_user.id)},
        )

        # Then only the second user's character is returned
        assert response.status_code == HTTP_200_OK
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == str(character_different_user.id)

    async def test_list_characters_with_results_specify_user_creator_id(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify filtering by user_creator_id returns only characters created by that user."""
        # Given characters created by different users
        second_user = await user_factory(company=session_company)
        await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        character_by_second = await character_factory(
            company=session_company,
            user_creator=second_user,
            user_player=second_user,
            campaign=session_campaign,
        )

        # When we filter by user_creator_id
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=session_company.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            params={
                "campaign_id": str(session_campaign.id),
                "user_creator_id": str(second_user.id),
            },
        )

        # Then only the character created by second_user is returned
        assert response.status_code == HTTP_200_OK
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == str(character_by_second.id)

    async def test_list_characters_with_results_specify_user_type(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify filtering by character_type returns only matching characters."""
        # Given a player character and a storyteller character
        await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            type=CharacterType.PLAYER,
        )
        character_storyteller = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            type=CharacterType.STORYTELLER,
        )

        # When we filter by STORYTELLER type
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=session_company.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            params={
                "campaign_id": str(session_campaign.id),
                "character_type": CharacterType.STORYTELLER.value,
            },
        )

        # Then only the storyteller character is returned
        assert response.status_code == HTTP_200_OK
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == str(character_storyteller.id)

    async def test_list_characters_with_results_specify_character_class(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify filtering by character_class returns only matching characters."""
        # Given a vampire and a mortal character
        character_vampire = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            character_class=CharacterClass.VAMPIRE,
        )
        await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            character_class=CharacterClass.MORTAL,
        )

        # When we filter by VAMPIRE class
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=session_company.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            params={
                "campaign_id": str(session_campaign.id),
                "character_class": CharacterClass.VAMPIRE.value,
            },
        )

        # Then only the vampire character is returned
        assert response.status_code == HTTP_200_OK
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == str(character_vampire.id)

    async def test_list_characters_with_results_specify_character_status(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify filtering by status returns only matching characters."""
        # Given an alive and a dead character
        await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        character_dead = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            status=CharacterStatus.DEAD,
        )

        # When we filter by DEAD status
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=session_company.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            params={"campaign_id": str(session_campaign.id), "status": CharacterStatus.DEAD.value},
        )

        # Then only the dead character is returned
        assert response.status_code == HTTP_200_OK
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == str(character_dead.id)

    async def test_list_characters_with_results_specify_show_temporary(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify filtering by is_temporary returns only temporary characters."""
        # Given a normal and a temporary character
        await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        character_temporary = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            is_temporary=True,
        )

        # When we filter by is_temporary=True
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=session_company.id,
            ),
            params={"campaign_id": str(session_campaign.id), "is_temporary": True},
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then only the temporary character is returned
        assert response.status_code == HTTP_200_OK
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == str(character_temporary.id)


class TestCharacterController:
    """Test character controller."""

    async def test_get_character(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify getting a character by ID."""
        # Given a character
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )

        # When we get the character
        response = await client.get(
            build_url(
                CharacterURL.DETAIL,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then we get the character data
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["id"] == str(character.id)
        assert data["name_first"] == character.name_first
        assert data["name_last"] == character.name_last
        _assert_character_response_shape(data)

    async def test_get_character_not_found(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify 404 when getting a character that does not exist."""
        # Given a non-existent character ID
        fake_id = uuid4()

        # When we try to get it
        response = await client.get(
            build_url(
                CharacterURL.DETAIL,
                company_id=session_company.id,
                character_id=fake_id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then we get a 404
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Character not found"

    async def test_get_character_no_include_omits_children(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify getCharacter without include param omits child resource keys."""
        # Given a character
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )

        # When we get the character without include
        response = await client.get(
            build_url(
                CharacterURL.DETAIL,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then the response has base fields but no child keys
        assert response.status_code == HTTP_200_OK
        data = response.json()
        _assert_character_response_shape(data)
        assert "traits" not in data
        assert "inventory" not in data
        assert "notes" not in data
        assert "assets" not in data

    async def test_get_character_include_traits(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        character_trait_factory,
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify getCharacter with include=traits embeds traits and omits other children."""
        # Given a character with a trait
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        trait = await character_trait_factory(character=character)

        # When we get the character with include=traits
        response = await client.get(
            build_url(
                CharacterURL.DETAIL,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            params={"include": ["traits"]},
        )

        # Then traits are embedded and other children are absent
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert "traits" in data
        assert len(data["traits"]) == 1
        assert data["traits"][0]["id"] == str(trait.id)
        assert "inventory" not in data
        assert "notes" not in data
        assert "assets" not in data

    async def test_get_character_include_all_children(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        character_trait_factory,
        character_inventory_factory,
        note_factory,
        s3asset_factory,
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify getCharacter with all includes embeds all four child lists."""
        # Given a character with one of each child type
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        trait = await character_trait_factory(character=character)
        item = await character_inventory_factory(character=character)
        note = await note_factory(company=session_company, character=character)
        asset = await s3asset_factory(
            company=session_company, character=character, uploaded_by=session_user
        )

        # When we include all four child types
        response = await client.get(
            build_url(
                CharacterURL.DETAIL,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            params={"include": ["traits", "inventory", "notes", "assets"]},
        )

        # Then all four child lists are present
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert len(data["traits"]) == 1
        assert data["traits"][0]["id"] == str(trait.id)
        assert len(data["inventory"]) == 1
        assert data["inventory"][0]["id"] == str(item.id)
        assert len(data["notes"]) == 1
        assert data["notes"][0]["id"] == str(note.id)
        assert len(data["assets"]) == 1
        assert data["assets"][0]["id"] == str(asset.id)

    async def test_get_character_include_empty_children(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify included children with no data return empty lists, not absent keys."""
        # Given a character with no children
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )

        # When we request all includes
        response = await client.get(
            build_url(
                CharacterURL.DETAIL,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            params={"include": ["traits", "inventory", "notes", "assets"]},
        )

        # Then all four child keys are present as empty lists
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["traits"] == []
        assert data["inventory"] == []
        assert data["notes"] == []
        assert data["assets"] == []

    async def test_get_character_include_excludes_archived_children(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        character_trait_factory,
        character_inventory_factory,
        note_factory,
        s3asset_factory,
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify getCharacter includes drop archived traits, inventory, notes, and assets."""
        # Given a character with one active and one archived of each child type
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        active_trait = await character_trait_factory(character=character)
        archived_trait = await character_trait_factory(character=character)
        archived_trait.is_archived = True
        await archived_trait.save()

        active_item = await character_inventory_factory(character=character)
        archived_item = await character_inventory_factory(character=character)
        archived_item.is_archived = True
        await archived_item.save()

        active_note = await note_factory(company=session_company, character=character)
        archived_note = await note_factory(company=session_company, character=character)
        archived_note.is_archived = True
        await archived_note.save()

        active_asset = await s3asset_factory(
            company=session_company, character=character, uploaded_by=session_user
        )
        archived_asset = await s3asset_factory(
            company=session_company, character=character, uploaded_by=session_user
        )
        archived_asset.is_archived = True
        await archived_asset.save()

        # When we include every child type
        response = await client.get(
            build_url(
                CharacterURL.DETAIL,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            params={"include": ["traits", "inventory", "notes", "assets"]},
        )

        # Then each list contains only the active child
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert [t["id"] for t in data["traits"]] == [str(active_trait.id)]
        assert [i["id"] for i in data["inventory"]] == [str(active_item.id)]
        assert [n["id"] for n in data["notes"]] == [str(active_note.id)]
        assert [a["id"] for a in data["assets"]] == [str(active_asset.id)]

    async def test_get_character_include_invalid_value(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify invalid include value returns 400."""
        # Given a character
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )

        # When we pass an invalid include value
        response = await client.get(
            build_url(
                CharacterURL.DETAIL,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            params={"include": ["bogus"]},
        )

        # Then we get a 400
        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_patch_character(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify patching a character updates the specified fields."""
        # Given a character
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        original_name_last = character.name_last

        # When we patch the character
        response = await client.patch(
            build_url(
                CharacterURL.UPDATE,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={
                "name_first": "Updated name",
                "status": "DEAD",
            },
        )

        # Then the character is updated
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["name_first"] == "Updated name"
        assert data["name_last"] == original_name_last
        assert data["status"] == CharacterStatus.DEAD.value
        assert data["date_killed"] is not None

        # And the DB reflects the change
        updated = await Character.get(id=character.id)
        assert updated.name_first == "Updated name"
        assert updated.status == CharacterStatus.DEAD

    async def test_delete_character(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify deleting a character archives it."""
        # Given a character
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )

        # When we delete the character
        response = await client.delete(
            build_url(
                CharacterURL.DELETE,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then we get 204
        assert response.status_code == HTTP_204_NO_CONTENT

        # And the character is now archived
        await character.refresh_from_db()
        assert character.is_archived

        # And GET returns 404
        response = await client.get(
            build_url(
                CharacterURL.DETAIL,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )
        assert response.status_code == HTTP_404_NOT_FOUND


class TestVampireAttributes:
    """Test vampire attributes."""

    async def test_create_character_vampire(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify creating a vampire character populates clan attributes."""
        # Given a vampire clan from seed data
        vampire_clan = await VampireClan.filter(is_archived=False, bane_name__isnull=False).first()
        assert vampire_clan is not None

        # When we create a vampire character
        response = await client.post(
            build_url(
                CharacterURL.CREATE,
                company_id=session_company.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={
                "name_first": "Test",
                "name_last": "Character",
                "name_nick": "The Pencil",
                "character_class": "VAMPIRE",
                "game_version": "V5",
                "type": "PLAYER",
                "campaign_id": str(session_campaign.id),
                "vampire_attributes": {
                    "clan_id": str(vampire_clan.id),
                },
            },
        )

        # Then the character is created with clan attributes
        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        _assert_character_response_shape(data)
        assert data["vampire_attributes"] is not None
        assert data["vampire_attributes"]["clan_id"] == str(vampire_clan.id)
        assert data["vampire_attributes"]["clan_name"] == vampire_clan.name
        assert data["vampire_attributes"]["bane_name"] in [
            vampire_clan.bane_name,
            vampire_clan.variant_bane_name,
        ]
        assert data["vampire_attributes"]["compulsion_name"] == vampire_clan.compulsion_name

    async def test_update_vampire_sire_and_generation(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        vampire_attributes_factory: Callable[..., VampireAttributes],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify updating a vampire character's sire and generation."""
        # Given a vampire character with clan attributes
        vampire_clan = await VampireClan.filter(is_archived=False).first()
        assert vampire_clan is not None
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            character_class=CharacterClass.VAMPIRE,
        )
        await vampire_attributes_factory(character=character, clan=vampire_clan)

        # When we update sire and generation
        response = await client.patch(
            build_url(
                CharacterURL.UPDATE,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={
                "name_first": "Updated name",
                "vampire_attributes": {"sire": "Updated Sire", "generation": 22},
            },
        )

        # Then the character is updated
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["name_first"] == "Updated name"
        assert data["vampire_attributes"]["sire"] == "Updated Sire"
        assert data["vampire_attributes"]["generation"] == 22
        assert data["vampire_attributes"]["clan_id"] == str(vampire_clan.id)
        assert data["vampire_attributes"]["clan_name"] == vampire_clan.name

    async def test_update_character_vampire_clan(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        vampire_attributes_factory: Callable[..., VampireAttributes],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify updating a vampire character's clan replaces clan-derived attributes."""
        # Given a vampire character with a clan
        original_clan = await VampireClan.filter(is_archived=False).first()
        assert original_clan is not None
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            character_class=CharacterClass.VAMPIRE,
        )
        await vampire_attributes_factory(
            character=character, clan=original_clan, sire="Original Sire"
        )

        # And a different clan
        new_clan = (
            await VampireClan.filter(
                is_archived=False,
            )
            .exclude(id=original_clan.id)
            .first()
        )
        assert new_clan is not None

        # When we update the clan
        response = await client.patch(
            build_url(
                CharacterURL.UPDATE,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={"vampire_attributes": {"clan_id": str(new_clan.id)}},
        )

        # Then the clan is updated but sire is preserved
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["vampire_attributes"]["clan_id"] == str(new_clan.id)
        assert data["vampire_attributes"]["clan_name"] == new_clan.name
        assert data["vampire_attributes"]["sire"] == "Original Sire"
        assert data["vampire_attributes"]["bane_name"] in [
            new_clan.bane_name,
            new_clan.variant_bane_name,
        ]
        assert data["vampire_attributes"]["compulsion_name"] == new_clan.compulsion_name

    async def test_update_vampire_bane_and_compulsion(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        vampire_attributes_factory: Callable[..., VampireAttributes],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify updating a vampire character's bane sends the correct response."""
        # Given a vampire character with clan attributes
        original_clan = await VampireClan.filter(is_archived=False, bane_name__isnull=False).first()
        assert original_clan is not None
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            character_class=CharacterClass.VAMPIRE,
        )
        await vampire_attributes_factory(
            character=character,
            clan=original_clan,
            bane_name=original_clan.bane_name,
            bane_description=original_clan.bane_description,
            compulsion_name=original_clan.compulsion_name,
            compulsion_description=original_clan.compulsion_description,
        )

        # When we send a patch with bane_name set to the variant
        response = await client.patch(
            build_url(
                CharacterURL.UPDATE,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={
                "vampire_attributes": {
                    "bane_name": original_clan.variant_bane_name,
                    "bane_description": original_clan.variant_bane_description,
                },
            },
        )

        # Then the response succeeds
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["vampire_attributes"]["clan_id"] == str(original_clan.id)
        assert data["vampire_attributes"]["clan_name"] == original_clan.name


class TestWerewolfAttributes:
    """Test werewolf attributes."""

    async def test_create_character_werewolf(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify creating a werewolf character populates tribe and auspice attributes."""
        # Given seed data
        werewolf_tribe = await WerewolfTribe.filter(is_archived=False).first()
        werewolf_auspice = await WerewolfAuspice.filter(is_archived=False).first()
        assert werewolf_tribe is not None
        assert werewolf_auspice is not None

        # When we create a werewolf character
        response = await client.post(
            build_url(
                CharacterURL.CREATE,
                company_id=session_company.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={
                "name_first": "Test",
                "name_last": "Character",
                "character_class": "WEREWOLF",
                "game_version": "V5",
                "type": "PLAYER",
                "campaign_id": str(session_campaign.id),
                "werewolf_attributes": {
                    "tribe_id": str(werewolf_tribe.id),
                    "auspice_id": str(werewolf_auspice.id),
                },
            },
        )

        # Then the character is created with tribe and auspice
        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        _assert_character_response_shape(data)
        assert data["werewolf_attributes"] is not None
        assert data["werewolf_attributes"]["tribe_id"] == str(werewolf_tribe.id)
        assert data["werewolf_attributes"]["tribe_name"] == werewolf_tribe.name
        assert data["werewolf_attributes"]["auspice_id"] == str(werewolf_auspice.id)
        assert data["werewolf_attributes"]["auspice_name"] == werewolf_auspice.name

    async def test_update_character_werewolf(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        werewolf_attributes_factory: Callable[..., WerewolfAttributes],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify updating a werewolf character's tribe."""
        # Given a werewolf character
        tribe = await WerewolfTribe.filter(is_archived=False).first()
        auspice = await WerewolfAuspice.filter(is_archived=False).first()
        assert tribe is not None
        assert auspice is not None
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            character_class=CharacterClass.WEREWOLF,
        )
        await werewolf_attributes_factory(character=character, tribe=tribe, auspice=auspice)

        # And a different tribe
        new_tribe = await WerewolfTribe.filter(is_archived=False).exclude(id=tribe.id).first()
        assert new_tribe is not None

        # When we update the tribe
        response = await client.patch(
            build_url(
                CharacterURL.UPDATE,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={
                "name_first": "Updated name",
                "werewolf_attributes": {"tribe_id": str(new_tribe.id)},
            },
        )

        # Then the tribe is updated but auspice is preserved
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["name_first"] == "Updated name"
        assert data["werewolf_attributes"]["tribe_id"] == str(new_tribe.id)
        assert data["werewolf_attributes"]["tribe_name"] == new_tribe.name
        assert data["werewolf_attributes"]["auspice_id"] == str(auspice.id)

    async def test_patch_werewolf_tribe(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        werewolf_attributes_factory: Callable[..., WerewolfAttributes],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify patching werewolf tribe updates tribe but preserves auspice."""
        # Given a werewolf character with full attributes
        tribe = await WerewolfTribe.filter(is_archived=False).first()
        auspice = await WerewolfAuspice.filter(is_archived=False).first()
        assert tribe is not None
        assert auspice is not None
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            character_class=CharacterClass.WEREWOLF,
        )
        await werewolf_attributes_factory(character=character, tribe=tribe, auspice=auspice)

        # When we patch with a different tribe
        new_tribe = await WerewolfTribe.filter(is_archived=False).exclude(id=tribe.id).first()
        assert new_tribe is not None
        response = await client.patch(
            build_url(
                CharacterURL.UPDATE,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={
                "werewolf_attributes": {"tribe_id": str(new_tribe.id)},
            },
        )

        # Then tribe is changed but auspice is preserved
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["werewolf_attributes"]["tribe_id"] == str(new_tribe.id)
        assert data["werewolf_attributes"]["tribe_name"] == new_tribe.name
        assert data["werewolf_attributes"]["auspice_id"] == str(auspice.id)
        assert data["werewolf_attributes"]["auspice_name"] == auspice.name


class TestCharacterCreate:
    """Test character create endpoints."""

    async def test_create_character(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        trait_factory: Callable[..., Trait],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify creating a character with traits."""
        # Given traits from the Abilities section
        section = await CharSheetSection.filter(name="Abilities", is_archived=False).first()
        assert section is not None
        traits = await Trait.filter(
            sheet_section=section, is_archived=False, is_custom=False
        ).limit(3)
        assert len(traits) > 0
        trait_create_data = [{"trait_id": str(t.id), "value": 1} for t in traits]

        # When we create a character with those traits
        response = await client.post(
            build_url(
                CharacterURL.CREATE,
                company_id=session_company.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={
                "name_first": "Test",
                "name_last": "Character",
                "character_class": "MORTAL",
                "game_version": "V5",
                "type": "PLAYER",
                "campaign_id": str(session_campaign.id),
                "traits": trait_create_data,
            },
        )

        # Then the character is created
        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        _assert_character_response_shape(data)
        assert data["name_first"] == "Test"
        assert data["name_last"] == "Character"
        assert data["character_class"] == CharacterClass.MORTAL.value

        # And the traits are persisted

        ct_count = await CharacterTrait.filter(character_id=data["id"]).count()
        assert ct_count == len(traits)

    @pytest.mark.parametrize(
        "json_data",
        [
            ({"game_version": "INVALID"}),
            ({"type": "INVALID"}),
            ({"character_class": "INVALID"}),
            ({"concept_id": "INVALID"}),
            ({"user_player_id": "INVALID"}),
        ],
    )
    async def test_create_character_invalid_parameters(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        json_data: dict[str, str],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify 400 when creating a character with invalid parameters."""
        correct_json_data = {
            "name_first": "Test",
            "name_last": "Character",
            "character_class": "MORTAL",
            "game_version": "V5",
            "type": "PLAYER",
            "biography": "Test biography",
            "demeanor": "Test demeanor",
            "nature": "Test nature",
            "campaign_id": str(session_campaign.id),
        }
        base_json_data = {**correct_json_data, **json_data}

        response = await client.post(
            build_url(
                CharacterURL.CREATE,
                company_id=session_company.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json=base_json_data,
        )
        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_create_character_with_explicit_user_player(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        user_factory: Callable[..., User],
        session_campaign: Campaign,
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify creating a character with an explicit user_player_id succeeds."""
        # Given another user in the company
        other_user = await user_factory(company=session_company)

        # When we create a character with an explicit user_player_id
        response = await client.post(
            build_url(
                CharacterURL.CREATE,
                company_id=session_company.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={
                "name_first": "Test explicit player",
                "name_last": "Character",
                "character_class": "MORTAL",
                "game_version": "V5",
                "type": "PLAYER",
                "campaign_id": str(session_campaign.id),
                "user_player_id": str(other_user.id),
            },
        )

        # Then the character is created with the specified user_player_id
        assert response.status_code == HTTP_201_CREATED
        assert response.json()["user_player_id"] == str(other_user.id)

    async def test_create_character_with_everything(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        user_factory: Callable[..., User],
        character_concept_factory: Callable[..., CharacterConcept],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify creating a character with all optional fields."""
        # Given a second user to be the player, a concept, and a vampire clan
        user_player = await user_factory(company=session_company)
        vampire_clan = await VampireClan.filter(is_archived=False).first()
        assert vampire_clan is not None
        concept = await character_concept_factory()

        # And some traits from the Attributes section
        section = await CharSheetSection.filter(name="Attributes", is_archived=False).first()
        assert section is not None
        traits = await Trait.filter(
            sheet_section=section, is_archived=False, is_custom=False
        ).limit(5)
        trait_create_data = [{"trait_id": str(t.id), "value": 0} for t in traits]

        # When we create a character with everything
        response = await client.post(
            build_url(
                CharacterURL.CREATE,
                company_id=session_company.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={
                "name_first": "Test",
                "name_last": "Character",
                "name_nick": "The Pencil",
                "age": 20,
                "biography": "Test biography",
                "demeanor": "Test demeanor",
                "nature": "Test nature",
                "character_class": "VAMPIRE",
                "game_version": "V5",
                "type": "PLAYER",
                "campaign_id": str(session_campaign.id),
                "traits": trait_create_data,
                "vampire_attributes": {
                    "clan_id": str(vampire_clan.id),
                    "sire": "Test Sire",
                    "generation": 1,
                },
                "concept_id": str(concept.id),
                "user_player_id": str(user_player.id),
            },
        )

        # Then the character is created with all fields
        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        _assert_character_response_shape(data)
        assert data["name_first"] == "Test"
        assert data["name_last"] == "Character"
        assert data["name_nick"] == "The Pencil"
        assert data["age"] == 20
        assert data["biography"] == "Test biography"
        assert data["demeanor"] == "Test demeanor"
        assert data["nature"] == "Test nature"
        assert data["character_class"] == CharacterClass.VAMPIRE.value
        assert data["vampire_attributes"]["clan_id"] == str(vampire_clan.id)
        assert data["vampire_attributes"]["clan_name"] == vampire_clan.name
        assert data["vampire_attributes"]["sire"] == "Test Sire"
        assert data["vampire_attributes"]["generation"] == 1
        assert data["concept_id"] == str(concept.id)
        assert data["concept_name"] == concept.name
        assert data["user_player_id"] == str(user_player.id)

        # And the character has the correct trait count in DB

        ct_count = await CharacterTrait.filter(character_id=data["id"]).count()
        assert ct_count >= len(traits)


class TestCharacterFullSheet:
    """Test character full sheet endpoint."""

    async def test_get_character_full_sheet(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        character_trait_factory: Callable,
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify the full sheet endpoint returns the character with organized sections."""
        # Given a character with traits
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        trait_no_sub = await Trait.filter(is_archived=False, subcategory_id__isnull=True).first()
        trait_with_sub = await Trait.filter(is_archived=False, subcategory_id__isnull=False).first()
        assert trait_no_sub is not None
        assert trait_with_sub is not None

        await character_trait_factory(character=character, trait=trait_no_sub, value=3)
        await character_trait_factory(character=character, trait=trait_with_sub, value=2)

        # When we request the full sheet
        response = await client.get(
            build_url(
                CharacterURL.FULL_SHEET,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then the response is successful
        assert response.status_code == HTTP_200_OK
        data = response.json()

        # And the response contains the character
        assert data["character"]["id"] == str(character.id)

        # And sections are present and structured correctly
        assert len(data["sections"]) >= 1
        for section in data["sections"]:
            assert "id" in section
            assert "name" in section
            assert "categories" in section
            for category in section["categories"]:
                assert "id" in category
                assert "name" in category
                assert "subcategories" in category
                assert "character_traits" in category
                for sub in category["subcategories"]:
                    assert "id" in sub
                for ct in category["character_traits"]:
                    assert "id" in ct
                    assert "character_id" in ct

    async def test_get_character_full_sheet_with_available_traits(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        character_trait_factory: Callable,
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify the full sheet endpoint includes available traits when flag is set."""
        # Given a character with one assigned trait
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        assigned_trait = await Trait.filter(
            is_archived=False,
            subcategory_id__isnull=True,
            character_classes__contains=[character.character_class.value],
            game_versions__contains=[character.game_version.value],
            is_custom=False,
        ).first()
        assert assigned_trait is not None
        await character_trait_factory(character=character, trait=assigned_trait, value=3)

        # When we request the full sheet with include_available_traits=true
        url = build_url(
            CharacterURL.FULL_SHEET,
            company_id=session_company.id,
            character_id=character.id,
        )
        response = await client.get(
            f"{url}?include_available_traits=true",
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then the response is successful
        assert response.status_code == HTTP_200_OK
        data = response.json()

        # And available_traits fields are present on categories and subcategories
        for section in data["sections"]:
            for category in section["categories"]:
                assert "available_traits" in category
                assert isinstance(category["available_traits"], list)
                for sub in category["subcategories"]:
                    assert "available_traits" in sub
                    assert isinstance(sub["available_traits"], list)

        # And the assigned trait does not appear in any available_traits list
        all_available_ids = set()
        for section in data["sections"]:
            for category in section["categories"]:
                all_available_ids.update(t["id"] for t in category["available_traits"])
                for sub in category["subcategories"]:
                    all_available_ids.update(t["id"] for t in sub["available_traits"])
        assert str(assigned_trait.id) not in all_available_ids

        # And at least some available traits are present
        assert len(all_available_ids) > 0

    async def test_get_character_full_sheet_available_traits_empty_by_default(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify available_traits is empty when include_available_traits is not set."""
        # Given a character
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )

        # When we request the full sheet without the flag
        response = await client.get(
            build_url(
                CharacterURL.FULL_SHEET,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then all available_traits lists are empty
        assert response.status_code == HTTP_200_OK
        data = response.json()
        for section in data["sections"]:
            for category in section["categories"]:
                assert category["available_traits"] == []
                for sub in category["subcategories"]:
                    assert sub["available_traits"] == []

    async def test_get_character_full_sheet_category(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        character_trait_factory: Callable,
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify the category slice endpoint returns a single category with traits."""
        # Given a trait without a subcategory
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        trait_no_sub = await Trait.filter(is_archived=False, subcategory_id__isnull=True).first()
        assert trait_no_sub is not None
        await character_trait_factory(character=character, trait=trait_no_sub, value=3)

        # When we request that trait's category
        response = await client.get(
            build_url(
                CharacterURL.FULL_SHEET_CATEGORY,
                company_id=session_company.id,
                character_id=character.id,
                category_id=str(trait_no_sub.category_id),  # type: ignore[attr-defined]
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then the response is successful
        assert response.status_code == HTTP_200_OK
        data = response.json()

        # And the response contains the category with correct structure
        assert data["id"] == str(trait_no_sub.category_id)  # type: ignore[attr-defined]
        assert "name" in data
        assert "subcategories" in data
        assert "character_traits" in data

        # And the character trait is present
        trait_ids = [ct["trait"]["id"] for ct in data["character_traits"]]
        assert str(trait_no_sub.id) in trait_ids

    async def test_get_character_full_sheet_category_with_available_traits(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        character_trait_factory: Callable,
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify the category slice includes available traits when requested."""
        # Given a trait assigned to the character
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        trait = await Trait.filter(
            is_archived=False, subcategory_id__isnull=True, is_custom=False
        ).first()
        assert trait is not None
        await character_trait_factory(character=character, trait=trait, value=2)

        # When we request the category with available traits
        response = await client.get(
            build_url(
                CharacterURL.FULL_SHEET_CATEGORY,
                company_id=session_company.id,
                character_id=character.id,
                category_id=str(trait.category_id),  # type: ignore[attr-defined]
            ),
            params={"include_available_traits": True},
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then the response is successful
        assert response.status_code == HTTP_200_OK
        data = response.json()

        # And available_traits is populated
        all_available = data.get("available_traits", [])
        for sub in data.get("subcategories", []):
            all_available.extend(sub.get("available_traits", []))

        # And the assigned trait is NOT in available_traits
        available_ids = [t["id"] for t in all_available]
        assert str(trait.id) not in available_ids

    async def test_get_character_full_sheet_category_available_traits_default_empty(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify available traits are empty when not requested."""
        # Given a character and a category
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        category = await TraitCategory.filter(is_archived=False).first()
        assert category is not None

        # When we request without include_available_traits
        response = await client.get(
            build_url(
                CharacterURL.FULL_SHEET_CATEGORY,
                company_id=session_company.id,
                character_id=character.id,
                category_id=str(category.id),
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then available traits lists are all empty
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["available_traits"] == []
        for sub in data.get("subcategories", []):
            assert sub["available_traits"] == []

    async def test_get_character_full_sheet_category_not_found(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify 404 when category does not exist."""
        # Given a character and a non-existent category ID
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        fake_id = uuid4()

        # When we request it
        response = await client.get(
            build_url(
                CharacterURL.FULL_SHEET_CATEGORY,
                company_id=session_company.id,
                character_id=character.id,
                category_id=str(fake_id),
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then we get a 404
        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_get_character_full_sheet_category_empty_skeleton(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify an empty category returns the skeleton structure."""
        # Given a character and a category with show_when_empty=True
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        category = await TraitCategory.filter(is_archived=False, show_when_empty=True).first()
        assert category is not None

        # When we request that category
        response = await client.get(
            build_url(
                CharacterURL.FULL_SHEET_CATEGORY,
                company_id=session_company.id,
                character_id=character.id,
                category_id=str(category.id),
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then the response includes the category structure
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["id"] == str(category.id)
        assert data["show_when_empty"] is True
        assert "subcategories" in data
        assert "character_traits" in data

    async def test_get_character_full_sheet_category_out_of_class(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable[..., Character],
        character_trait_factory: Callable,
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
    ) -> None:
        """Verify out-of-class category returns traits granted by storyteller."""
        # Given a character
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            character_class=CharacterClass.MORTAL,
        )

        # And a trait from a different character class than the character
        trait = (
            await Trait.filter(
                is_archived=False,
                subcategory_id__isnull=True,
            )
            .exclude(
                character_classes__contains=[CharacterClass.MORTAL.value],
            )
            .first()
        )
        assert trait is not None

        # And the trait is assigned to the character (storyteller grant)
        await character_trait_factory(character=character, trait=trait, value=1)

        # When we request that trait's category
        response = await client.get(
            build_url(
                CharacterURL.FULL_SHEET_CATEGORY,
                company_id=session_company.id,
                character_id=character.id,
                category_id=str(trait.category_id),  # type: ignore[attr-defined]
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then the response is successful and includes the out-of-class trait
        assert response.status_code == HTTP_200_OK
        data = response.json()
        trait_ids = [ct["trait"]["id"] for ct in data["character_traits"]]
        assert str(trait.id) in trait_ids
