"""Test character trait controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import ANY

import pytest
from beanie import PydanticObjectId
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from vapi.constants import UserRole
from vapi.db.models import Character, CharacterTrait, Trait, TraitCategory
from vapi.domain.services import CharacterTraitService, GetModelByIdValidationService
from vapi.domain.urls import Characters

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.models import User

pytestmark = pytest.mark.anyio


class TestFetchingCharacterTraits:
    """Test fetching character traits."""

    async def test_list_character_trait_with_traits_by_parent_category_id(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_character: Character,
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        trait_factory: Callable[[dict[str, ...]], Trait],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Test character trait controller."""
        trait_categories = await TraitCategory.find(TraitCategory.is_archived == False).to_list()
        trait1 = await trait_factory(parent_category_id=trait_categories[0].id)
        trait2 = await trait_factory(parent_category_id=trait_categories[1].id)

        character_trait1 = await character_trait_factory(
            character_id=base_character.id, trait=trait1
        )
        await character_trait_factory(character_id=base_character.id, trait=trait2)

        response = await client.get(
            build_url(Characters.TRAITS),
            headers=token_company_admin,
            params={"parent_category_id": str(trait_categories[0].id)},
        )
        # debug(response.json())
        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == 1
        assert response.json()["limit"] == 10
        assert response.json()["offset"] == 0
        assert response.json()["items"] == [character_trait1.model_dump(mode="json")]

        # cleanup non-constant traits
        await trait1.delete()
        await trait2.delete()

    async def test_get_character_trait(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_character: Character,
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Test character trait controller."""
        character_trait = await character_trait_factory(character_id=base_character.id)
        response = await client.get(
            build_url(Characters.TRAIT_DETAIL, character_trait_id=character_trait.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == character_trait.model_dump(mode="json")

    async def test_get_character_trait_not_found(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Test character trait controller."""
        response = await client.get(
            build_url(Characters.TRAIT_DETAIL, character_trait_id=PydanticObjectId()),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Character trait not found"

        async def test_add_constant_trait_to_character(
            client: AsyncClient,
            build_url: Callable[[str, ...], str],
            base_character: Character,
            token_company_admin: dict[str, str],
            debug: Callable[[...], None],
        ) -> None:
            """Test adding a constant trait to a character."""
            trait = await Trait.find_one(Trait.is_archived == False)
            response = await client.post(
                build_url(Characters.TRAIT_ASSIGN),
                headers=token_company_admin,
                json={"trait_id": str(trait.id), "value": 1},
            )
            assert response.status_code == HTTP_201_CREATED
            assert response.json() == {
                "character_id": str(base_character.id),
                "id": response.json()["id"],
                "trait": trait.model_dump(mode="json"),
                "value": 1,
            }
            character_trait_id = response.json()["id"]

            response = await client.get(
                build_url(Characters.TRAIT_DETAIL, character_trait_id=character_trait_id),
                headers=token_company_admin,
            )
            assert response.status_code == HTTP_200_OK
            assert response.json() == {
                "character_id": str(base_character.id),
                "id": character_trait_id,
                "trait": trait.model_dump(mode="json"),
                "value": 1,
            }

            response = await client.get(build_url(Characters.TRAITS), headers=token_company_admin)
            assert response.status_code == HTTP_200_OK
            assert response.json()["items"] == [
                {
                    "character_id": str(base_character.id),
                    "id": character_trait_id,
                    "trait": trait.model_dump(mode="json"),
                    "value": 1,
                }
            ]
            assert response.json()["total"] == 1
            assert response.json()["limit"] == 10
            assert response.json()["offset"] == 0


class TestAddConstantTraitToCharacter:
    """Test adding a constant trait to a character."""

    async def test_add_constant_trait_to_character(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_character: Character,
        token_company_admin: dict[str, str],
        mocker: Any,
        debug: Callable[[...], None],
    ) -> None:
        """Test character trait controller."""
        trait = await Trait.find_one(Trait.is_archived == False)
        trait_spy = mocker.spy(GetModelByIdValidationService, "get_trait_by_id")
        character_trait_spy = mocker.spy(CharacterTraitService, "after_save")

        # When adding the trait to a character
        response = await client.post(
            build_url(Characters.TRAIT_ASSIGN),
            headers=token_company_admin,
            json={"trait_id": str(trait.id), "value": 1},
        )

        # Then the response is correct and the trait is added
        assert response.status_code == HTTP_201_CREATED
        character_trait_id = response.json()["id"]
        character_trait = await CharacterTrait.get(character_trait_id, fetch_links=True)
        assert response.json() == character_trait.model_dump(mode="json")
        assert character_trait.value == 1
        assert character_trait.trait.id == trait.id
        assert character_trait.character_id == base_character.id
        assert character_trait.trait.max_value == trait.max_value
        assert not character_trait.trait.custom_for_character_id

        trait_spy.assert_called_once_with(ANY, trait.id)
        character_trait_spy.assert_called_once_with(ANY, character_trait)


class TestCustomTraits:
    """Test custom traits."""

    @pytest.mark.clean_db
    async def test_create_custom(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_global_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify that creating a custom trait works."""
        trait_category = await TraitCategory.find_one(TraitCategory.is_archived == False)
        custom_trait_data = {
            "name": "Test Trait",
            "description": "Test Description",
            "max_value": 5,
            "min_value": 0,
            "show_when_zero": True,
            "parent_category_id": str(trait_category.id),
            "initial_cost": 10,
            "upgrade_cost": 10,
        }

        response = await client.post(
            build_url(Characters.TRAIT_CREATE),
            headers=token_global_admin,
            json=custom_trait_data,
        )
        assert response.status_code == HTTP_201_CREATED

        created_custom_trait_id = response.json()["id"]
        created_custom_trait = await CharacterTrait.get(created_custom_trait_id, fetch_links=True)
        assert response.json() == created_custom_trait.model_dump(mode="json")
        assert created_custom_trait.value == 0
        assert created_custom_trait.trait.initial_cost == 10
        assert created_custom_trait.trait.upgrade_cost == 10
        assert created_custom_trait.trait.parent_category_id == trait_category.id
        assert created_custom_trait.trait.name == "Test Trait"
        assert created_custom_trait.trait.description == "Test Description"

    async def test_delete_character_trait(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_character: Character,
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify that deleting a character trait works."""
        character_trait = await character_trait_factory()
        trait = await Trait.get(character_trait.trait.id)
        character = await Character.get(base_character.id)
        assert character_trait.id in character.character_trait_ids

        response = await client.delete(
            build_url(Characters.TRAIT_DELETE, character_trait_id=character_trait.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_204_NO_CONTENT
        await character.sync()
        assert character_trait.id not in character.character_trait_ids
        assert not await CharacterTrait.find_one(CharacterTrait.id == character_trait.id)
        assert await Trait.get(trait.id) == trait

    async def test_delete_character_trait_custom(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_character: Character,
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify that deleting a custom character trait works."""
        character_trait = await character_trait_factory(is_custom=True)
        trait = await Trait.get(character_trait.trait.id)
        character = await Character.get(base_character.id)
        assert character_trait.id in character.character_trait_ids

        response = await client.delete(
            build_url(Characters.TRAIT_DELETE, character_trait_id=character_trait.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_204_NO_CONTENT
        await character.sync()
        assert character_trait.id not in character.character_trait_ids
        assert not await CharacterTrait.find_one(CharacterTrait.id == character_trait.id)
        assert not await Trait.find_one(Trait.id == trait.id)


class TestChangingCharacterTraitValue:
    """Test changing a character trait value."""

    @pytest.mark.parametrize(
        "user_role", [(UserRole.STORYTELLER), (UserRole.ADMIN), (UserRole.PLAYER)]
    )
    async def test_increase_character_trait_value(
        self,
        user_role: UserRole,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_character: Character,
        user_factory: Callable[[dict[str, ...]], User],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify that increasing a character trait value works."""
        # Setup the trait and character trait and user experience
        user = await user_factory(role=user_role)

        trait = await Trait.find_one(Trait.is_archived == False)
        character_trait = await character_trait_factory(value=0, trait=trait)
        await user.update_campaign_experience(
            campaign_id=base_character.campaign_id,
            updates={"xp_current": 100, "xp_total": 100},
        )

        # When increasing the trait value by 1, the experience cost is the initial cost
        response = await client.put(
            build_url(
                Characters.TRAIT_INCREASE, character_trait_id=character_trait.id, user_id=user.id
            ),
            headers=token_company_admin,
            json={"num_dots": 1},
        )
        if user_role == UserRole.PLAYER:
            assert response.status_code == HTTP_403_FORBIDDEN
            return

        assert response.status_code == HTTP_200_OK

        await character_trait.sync()
        assert response.json() == character_trait.model_dump(mode="json")
        assert character_trait.value == 1

        # Cleanup
        await user.delete()

    @pytest.mark.parametrize(
        "user_role", [(UserRole.STORYTELLER), (UserRole.ADMIN), (UserRole.PLAYER)]
    )
    async def test_decrease_character_trait_value(
        self,
        user_role: UserRole,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_character: Character,
        user_factory: Callable[[dict[str, ...]], User],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify that decreasing a character trait value works."""
        # Setup the trait and character trait and user experience
        user = await user_factory(role=user_role)
        trait = await Trait.find_one(Trait.is_archived == False)
        character_trait = await character_trait_factory(value=trait.max_value, trait=trait)

        response = await client.put(
            build_url(
                Characters.TRAIT_DECREASE, character_trait_id=character_trait.id, user_id=user.id
            ),
            headers=token_company_admin,
            json={"num_dots": 1},
        )
        if user_role == UserRole.PLAYER:
            assert response.status_code == HTTP_403_FORBIDDEN
            return

        assert response.status_code == HTTP_200_OK

        await character_trait.sync()
        assert response.json() == character_trait.model_dump(mode="json")
        assert character_trait.value == trait.max_value - 1

        # Cleanup
        await user.delete()

    async def test_purchase_character_trait_value_with_xp(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        user_factory: Callable[[dict[str, ...]], User],
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify that purchasing a character trait value with xp works."""
        # Setup the trait and character trait and user experience
        character_player_user = await user_factory(role=UserRole.PLAYER)
        character = await character_factory(user_player_id=character_player_user.id)

        trait = await Trait.find_one(Trait.is_archived == False)

        character_trait = await character_trait_factory(
            value=0, trait=trait, character_id=character.id
        )

        await character_player_user.add_xp(
            campaign_id=character.campaign_id,
            amount=100,
        )

        # When purchasing a trait value
        response = await client.put(
            build_url(
                Characters.TRAIT_XP_PURCHASE,
                character_id=character.id,
                character_trait_id=character_trait.id,
                user_id=character_player_user.id,
            ),
            headers=token_company_admin,
            json={"num_dots": 1},
        )
        # debug(response.json())

        # Then verify the response
        assert response.status_code == HTTP_200_OK

        await character_trait.sync()
        assert response.json() == character_trait.model_dump(mode="json")
        assert character_trait.value == 1
        await character_player_user.sync()
        campaign_experience = await character_player_user.get_or_create_campaign_experience(
            character.campaign_id
        )
        assert campaign_experience.xp_current == 100 - trait.initial_cost
        assert campaign_experience.xp_total == 100

        # Cleanup
        await character_player_user.delete()
        await character.delete()
        await character_trait.delete()

    async def test_purchase_character_trait_value_as_storyteller(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        user_factory: Callable[[dict[str, ...]], User],
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify that purchasing a character trait value as a storyteller works."""
        # Setup the trait and character trait and user experience
        storyteller_user = await user_factory(role=UserRole.STORYTELLER, name="Storyteller User")
        character_player_user = await user_factory(role=UserRole.PLAYER)
        character = await character_factory(user_player_id=character_player_user.id)

        trait = await Trait.find_one(Trait.is_archived == False)

        character_trait = await character_trait_factory(
            value=0, trait=trait, character_id=character.id
        )

        await character_player_user.add_xp(
            campaign_id=character.campaign_id,
            amount=100,
        )

        # When purchasing a character trait value with xp, the experience cost is the initial cost
        response = await client.put(
            build_url(
                Characters.TRAIT_XP_PURCHASE,
                character_id=character.id,
                character_trait_id=character_trait.id,
                user_id=storyteller_user.id,
            ),
            headers=token_company_admin,
            json={"num_dots": 1},
        )
        # debug(response.json())

        # Then verify the response
        assert response.status_code == HTTP_200_OK

        await character_trait.sync()
        assert response.json() == character_trait.model_dump(mode="json")
        assert character_trait.value == 1
        await character_player_user.sync()
        campaign_experience = await character_player_user.get_or_create_campaign_experience(
            character.campaign_id
        )
        assert campaign_experience.xp_current == 100 - trait.initial_cost
        assert campaign_experience.xp_total == 100

        # Cleanup
        await character_player_user.delete()
        await storyteller_user.delete()
        await character.delete()
        await character_trait.delete()

    async def test_purchase_character_trait_value_fail_as_player(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        user_factory: Callable[[dict[str, ...]], User],
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify that purchasing a character trait value fails as a player that does not own the character."""
        # Setup the trait and character trait and user experience
        player_user = await user_factory(role=UserRole.PLAYER, name="Player User")
        character_player_user = await user_factory(role=UserRole.PLAYER)
        character = await character_factory(user_player_id=character_player_user.id)

        trait = await Trait.find_one(Trait.is_archived == False)

        character_trait = await character_trait_factory(
            value=0, trait=trait, character_id=character.id
        )

        await character_player_user.add_xp(
            campaign_id=character.campaign_id,
            amount=100,
        )

        # When purchasing a character trait value with xp, the experience cost is the initial cost
        response = await client.put(
            build_url(
                Characters.TRAIT_XP_PURCHASE,
                character_id=character.id,
                character_trait_id=character_trait.id,
                user_id=player_user.id,
            ),
            headers=token_company_admin,
            json={"num_dots": 1},
        )
        # debug(response.json())

        # Then verify the response
        assert response.status_code == HTTP_403_FORBIDDEN

        # Cleanup
        await character_player_user.delete()
        await player_user.delete()
        await character.delete()
        await character_trait.delete()

    async def test_refund_character_trait_value_with_xp(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        user_factory: Callable[[dict[str, ...]], User],
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify that refunding a character trait value with xp works."""
        # Setup the trait and character trait and user experience
        character_player_user = await user_factory(role=UserRole.PLAYER)
        character = await character_factory(user_player_id=character_player_user.id)

        trait = await Trait.find_one(Trait.is_archived == False)

        character_trait = await character_trait_factory(
            value=trait.max_value, trait=trait, character_id=character.id
        )

        await character_player_user.add_xp(
            campaign_id=character.campaign_id,
            amount=100,
        )

        # When refunding a trait value
        response = await client.put(
            build_url(
                Characters.TRAIT_XP_REFUND,
                character_id=character.id,
                character_trait_id=character_trait.id,
                user_id=character_player_user.id,
            ),
            headers=token_company_admin,
            json={"num_dots": 1},
        )
        # debug(response.json())

        # Then verify the response
        assert response.status_code == HTTP_200_OK

        await character_trait.sync()
        assert response.json() == character_trait.model_dump(mode="json")
        assert character_trait.value == trait.max_value - 1
        await character_player_user.sync()
        campaign_experience = await character_player_user.get_or_create_campaign_experience(
            character.campaign_id
        )
        assert campaign_experience.xp_current == 100 + (trait.initial_cost * trait.max_value)
        assert campaign_experience.xp_total == 100

        # Cleanup
        await character_player_user.delete()
        await character.delete()
        await character_trait.delete()

    async def test_refund_character_trait_value_as_storyteller(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        user_factory: Callable[[dict[str, ...]], User],
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify that refunding a character trait value as a storyteller works."""
        # Setup the trait and character trait and user experience
        storyteller_user = await user_factory(role=UserRole.STORYTELLER, name="Storyteller User")
        character_player_user = await user_factory(role=UserRole.PLAYER)
        character = await character_factory(user_player_id=character_player_user.id)

        trait = await Trait.find_one(Trait.is_archived == False)

        character_trait = await character_trait_factory(
            value=trait.max_value, trait=trait, character_id=character.id
        )

        await character_player_user.add_xp(
            campaign_id=character.campaign_id,
            amount=100,
        )

        # When purchasing a character trait value with xp, the experience cost is the initial cost
        response = await client.put(
            build_url(
                Characters.TRAIT_XP_REFUND,
                character_id=character.id,
                character_trait_id=character_trait.id,
                user_id=storyteller_user.id,
            ),
            headers=token_company_admin,
            json={"num_dots": 1},
        )
        # debug(response.json())

        # Then verify the response
        assert response.status_code == HTTP_200_OK

        await character_trait.sync()
        assert response.json() == character_trait.model_dump(mode="json")
        assert character_trait.value == trait.max_value - 1
        await character_player_user.sync()
        campaign_experience = await character_player_user.get_or_create_campaign_experience(
            character.campaign_id
        )
        assert campaign_experience.xp_current == 125
        assert campaign_experience.xp_total == 100

        # Cleanup
        await character_player_user.delete()
        await storyteller_user.delete()
        await character.delete()
        await character_trait.delete()

    async def test_refund_character_trait_value_fail_as_player(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        user_factory: Callable[[dict[str, ...]], User],
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify that refunding a character trait value fails as a player that does not own the character."""
        # Setup the trait and character trait and user experience
        player_user = await user_factory(role=UserRole.PLAYER, name="Player User")
        character_player_user = await user_factory(role=UserRole.PLAYER)
        character = await character_factory(user_player_id=character_player_user.id)

        trait = await Trait.find_one(Trait.is_archived == False)

        character_trait = await character_trait_factory(
            value=0, trait=trait, character_id=character.id
        )

        await character_player_user.add_xp(
            campaign_id=character.campaign_id,
            amount=100,
        )

        # When purchasing a character trait value with xp, the experience cost is the initial cost
        response = await client.put(
            build_url(
                Characters.TRAIT_XP_REFUND,
                character_id=character.id,
                character_trait_id=character_trait.id,
                user_id=player_user.id,
            ),
            headers=token_company_admin,
            json={"num_dots": 1},
        )
        # debug(response.json())

        # Then verify the response
        assert response.status_code == HTTP_403_FORBIDDEN

        # Cleanup
        await character_player_user.delete()
        await player_user.delete()
        await character.delete()
        await character_trait.delete()


class TestUseStartingPoints:
    """Test using starting points to purchase character trait values."""

    async def test_purchase_character_trait_value_with_starting_points(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_user: User,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify that purchasing a character trait value with starting points works."""
        # Setup the trait and character trait and user experience
        character = await character_factory(starting_points=100)

        trait = await Trait.find_one(Trait.is_archived == False)

        character_trait = await character_trait_factory(
            value=0, trait=trait, character_id=character.id
        )

        # When purchasing a trait value with starting points
        response = await client.put(
            build_url(
                Characters.TRAIT_STARTINGPOINTS_PURCHASE,
                character_id=character.id,
                character_trait_id=character_trait.id,
                user_id=base_user.id,
            ),
            headers=token_company_admin,
            json={"num_dots": 1},
        )

        # Then verify the response
        assert response.status_code == HTTP_200_OK

        await character_trait.sync()
        assert response.json() == character_trait.model_dump(mode="json")
        assert character_trait.value == 1
        await character.sync()
        assert character.starting_points == 100 - trait.initial_cost

        # Cleanup
        await character.delete()
        await character_trait.delete()

    async def test_refund_character_trait_value_with_starting_points(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_user: User,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify that refunding a character trait value with starting points works."""
        # Setup the trait and character trait and user experience
        character = await character_factory(starting_points=100)
        trait = await Trait.find_one(Trait.is_archived == False)
        character_trait = await character_trait_factory(
            value=trait.max_value, trait=trait, character_id=character.id
        )

        # When refunding a trait value with starting points
        response = await client.put(
            build_url(
                Characters.TRAIT_STARTINGPOINTS_REFUND,
                character_id=character.id,
                character_trait_id=character_trait.id,
                user_id=base_user.id,
            ),
            headers=token_company_admin,
            json={"num_dots": 1},
        )

        # Then verify the response
        assert response.status_code == HTTP_200_OK

        await character_trait.sync()
        assert response.json() == character_trait.model_dump(mode="json")
        assert character_trait.value == trait.max_value - 1
        await character.sync()
        assert character.starting_points == 125

        # Cleanup
        await character.delete()
        await character_trait.delete()
