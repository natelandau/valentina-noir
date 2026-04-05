"""Test character trait controllers."""

from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from vapi.constants import TraitModifyCurrency, UserRole
from vapi.db.sql_models.character import Character, CharacterTrait
from vapi.db.sql_models.character_sheet import Trait, TraitCategory
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain.services import CharacterTraitService
from vapi.domain.services.user_svc import UserXPService
from vapi.domain.urls import Characters

pytestmark = pytest.mark.anyio


class TestFetchingCharacterTraits:
    """Test fetching character traits."""

    async def test_list_character_trait_with_traits_by_parent_category_id(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_user: User,
        session_campaign: Any,
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        trait_factory: Callable[..., Trait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify listing character traits filtered by parent category ID."""
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        trait_categories = await TraitCategory.filter(is_archived=False)
        trait1 = await trait_factory(category=trait_categories[0])
        trait2 = await trait_factory(category=trait_categories[1])

        character_trait1 = await character_trait_factory(character=character, trait=trait1)
        await character_trait_factory(character=character, trait=trait2)

        response = await client.get(
            build_url(
                Characters.TRAITS,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
            ),
            headers=token_global_admin,
            params={"parent_category_id": str(trait_categories[0].id)},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == 1
        assert response.json()["limit"] == 10
        assert response.json()["offset"] == 0
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == str(character_trait1.id)
        assert items[0]["value"] == character_trait1.value

    async def test_get_character_trait(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_user: User,
        session_campaign: Any,
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify getting a single character trait by ID."""
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        trait = await Trait.filter(is_archived=False).first()
        character_trait = await character_trait_factory(character=character, trait=trait)

        response = await client.get(
            build_url(
                Characters.TRAIT_DETAIL,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                character_trait_id=character_trait.id,
            ),
            headers=token_global_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["id"] == str(character_trait.id)
        assert response.json()["character_id"] == str(character.id)
        assert response.json()["value"] == character_trait.value
        assert "trait" in response.json()
        assert response.json()["trait"]["id"] == str(trait.id)

    async def test_get_character_trait_not_found(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_user: User,
        session_campaign: Any,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify getting a non-existent character trait returns 404."""
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        response = await client.get(
            build_url(
                Characters.TRAIT_DETAIL,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                character_trait_id=uuid4(),
            ),
            headers=token_global_admin,
        )
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Character trait not found"


class TestAddConstantTraitToCharacter:
    """Test adding a constant trait to a character."""

    async def test_add_constant_trait_to_character(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_user: User,
        session_campaign: Any,
        character_factory: Callable[..., Character],
        mocker: Any,
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify adding a constant trait to a character."""
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )

        # Find a trait not already on the character
        existing_cts = await CharacterTrait.filter(character_id=character.id)
        existing_trait_ids = [ct.trait_id for ct in existing_cts]
        trait = await Trait.filter(is_archived=False).exclude(id__in=existing_trait_ids).first()

        character_trait_spy = mocker.spy(CharacterTraitService, "after_save")

        # When adding the trait to a character
        response = await client.post(
            build_url(
                Characters.TRAIT_ASSIGN,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
            ),
            headers=token_global_admin,
            json={
                "trait_id": str(trait.id),
                "value": 1,
                "currency": TraitModifyCurrency.NO_COST.value,
            },
        )

        # Then the response is correct and the trait is added
        assert response.status_code == HTTP_201_CREATED
        character_trait_id = response.json()["id"]
        assert response.json()["value"] == 1
        assert response.json()["character_id"] == str(character.id)
        assert response.json()["trait"]["id"] == str(trait.id)
        assert response.json()["trait"]["max_value"] == trait.max_value

        # Verify persisted in DB
        ct = (
            await CharacterTrait.filter(id=character_trait_id)
            .prefetch_related(
                "trait", "trait__category", "trait__subcategory", "trait__sheet_section"
            )
            .first()
        )
        assert ct is not None
        assert ct.value == 1
        assert ct.trait_id == trait.id
        assert ct.character_id == character.id
        assert not ct.trait.custom_for_character_id

        character_trait_spy.assert_called_once()


class TestCustomTraits:
    """Test custom traits."""

    async def test_create_custom(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_user: User,
        session_campaign: Any,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify that creating a custom trait works."""
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        trait_category = await TraitCategory.filter(is_archived=False).first()
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
            build_url(
                Characters.TRAIT_CREATE,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
            ),
            headers=token_global_admin,
            json=custom_trait_data,
        )
        assert response.status_code == HTTP_201_CREATED

        created_custom_trait_id = response.json()["id"]
        ct = (
            await CharacterTrait.filter(id=created_custom_trait_id)
            .prefetch_related(
                "trait", "trait__category", "trait__subcategory", "trait__sheet_section"
            )
            .first()
        )
        assert ct is not None
        assert ct.value == 0
        assert ct.trait.initial_cost == 10
        assert ct.trait.upgrade_cost == 10
        assert ct.trait.category_id == trait_category.id
        assert ct.trait.name == "Test Trait"
        assert ct.trait.description == "Test Description"

        # Clean up the custom trait since it lives in the constant trait table
        # and won't be removed by per-test cleanup
        await ct.trait.delete()


class TestDeleteCharacterTrait:
    """Test deleting a character trait."""

    async def test_delete_character_trait(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_user: User,
        session_campaign: Any,
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify that deleting a character trait works."""
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        trait = await Trait.filter(is_archived=False).first()
        character_trait = await character_trait_factory(character=character, trait=trait)
        trait_id = character_trait.trait_id

        response = await client.delete(
            build_url(
                Characters.TRAIT_DELETE,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                character_trait_id=character_trait.id,
            ),
            headers=token_global_admin,
        )
        assert response.status_code == HTTP_204_NO_CONTENT
        assert not await CharacterTrait.filter(id=character_trait.id).exists()
        # Non-custom trait should still exist
        assert await Trait.filter(id=trait_id).exists()

    async def test_delete_character_trait_custom(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_user: User,
        session_campaign: Any,
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        trait_factory: Callable[..., Trait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify that deleting a custom character trait also deletes the trait."""
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        custom_trait = await trait_factory(
            is_custom=True,
            custom_for_character_id=character.id,
        )
        character_trait = await character_trait_factory(character=character, trait=custom_trait)
        custom_trait_id = custom_trait.id

        response = await client.delete(
            build_url(
                Characters.TRAIT_DELETE,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                character_trait_id=character_trait.id,
            ),
            headers=token_global_admin,
        )
        assert response.status_code == HTTP_204_NO_CONTENT
        assert not await CharacterTrait.filter(id=character_trait.id).exists()
        # Custom trait should also be deleted
        assert not await Trait.filter(id=custom_trait_id).exists()

    async def test_delete_character_trait_with_xp_refund(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_campaign: Any,
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify that deleting a trait with currency=XP refunds XP to the user."""
        # Given a character with a trait at max value and user with XP
        character_player_user = await user_factory(
            role=UserRole.PLAYER.value, company=session_company
        )
        character = await character_factory(
            company=session_company,
            user_player=character_player_user,
            user_creator=character_player_user,
            campaign=session_campaign,
        )
        trait = await Trait.filter(is_archived=False, min_value__gt=0).first()
        character_trait = await character_trait_factory(
            value=trait.max_value, trait=trait, character=character
        )
        initial_xp = 100
        user_svc = UserXPService()
        await user_svc.add_xp(character_player_user.id, character.campaign_id, initial_xp)

        # When deleting the trait with XP currency
        response = await client.delete(
            build_url(
                Characters.TRAIT_DELETE,
                company_id=session_company.id,
                user_id=character_player_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                character_trait_id=character_trait.id,
            ),
            headers=token_global_admin,
            params={"currency": "XP"},
        )

        # Then the trait is deleted and XP is refunded
        assert response.status_code == HTTP_204_NO_CONTENT
        assert not await CharacterTrait.filter(id=character_trait.id).exists()
        campaign_experience = await user_svc.get_or_create_campaign_experience(
            character_player_user.id, character.campaign_id
        )
        assert campaign_experience.xp_current > initial_xp
        assert campaign_experience.xp_total == initial_xp


class TestModifyTraitValue:
    """Test modifying character trait values using the new consolidated endpoint."""

    @pytest.mark.parametrize(
        "user_role", [(UserRole.STORYTELLER), (UserRole.ADMIN), (UserRole.PLAYER)]
    )
    async def test_increase_trait_value_no_cost(
        self,
        user_role: UserRole,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_campaign: Any,
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify increasing a trait value with NO_COST currency."""
        # Given a user whose role determines the permission check, and a character
        # owned by a different user so that PLAYER fails the ownership guard
        user = await user_factory(role=user_role.value, company=session_company)
        character_owner = await user_factory(role=UserRole.PLAYER.value, company=session_company)
        character = await character_factory(
            company=session_company,
            user_player=character_owner,
            user_creator=character_owner,
            campaign=session_campaign,
        )
        trait = await Trait.filter(is_archived=False).first()
        character_trait = await character_trait_factory(value=0, trait=trait, character=character)

        # When increasing the trait value with NO_COST
        response = await client.put(
            build_url(
                Characters.TRAIT_VALUE,
                company_id=session_company.id,
                user_id=user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                character_trait_id=character_trait.id,
            ),
            headers=token_global_admin,
            json={"target_value": 1, "currency": "NO_COST"},
        )

        # Then players should be forbidden (they don't own the character),
        # storytellers/admins should succeed
        if user_role == UserRole.PLAYER:
            assert response.status_code == HTTP_403_FORBIDDEN
        else:
            assert response.status_code == HTTP_200_OK
            updated_ct = await CharacterTrait.get(id=character_trait.id)
            assert updated_ct.value == 1

    @pytest.mark.parametrize(
        "user_role", [(UserRole.STORYTELLER), (UserRole.ADMIN), (UserRole.PLAYER)]
    )
    async def test_decrease_trait_value_no_cost(
        self,
        user_role: UserRole,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_campaign: Any,
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify decreasing a trait value with NO_COST currency."""
        # Given a user whose role determines the permission check, and a character
        # owned by a different user so that PLAYER fails the ownership guard
        user = await user_factory(role=user_role.value, company=session_company)
        character_owner = await user_factory(role=UserRole.PLAYER.value, company=session_company)
        character = await character_factory(
            company=session_company,
            user_player=character_owner,
            user_creator=character_owner,
            campaign=session_campaign,
        )
        trait = await Trait.filter(is_archived=False).first()
        character_trait = await character_trait_factory(
            value=trait.max_value, trait=trait, character=character
        )

        # When decreasing the trait value with NO_COST
        response = await client.put(
            build_url(
                Characters.TRAIT_VALUE,
                company_id=session_company.id,
                user_id=user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                character_trait_id=character_trait.id,
            ),
            headers=token_global_admin,
            json={"target_value": trait.max_value - 1, "currency": "NO_COST"},
        )

        # Then players should be forbidden (they don't own the character),
        # storytellers/admins should succeed
        if user_role == UserRole.PLAYER:
            assert response.status_code == HTTP_403_FORBIDDEN
        else:
            assert response.status_code == HTTP_200_OK
            updated_ct = await CharacterTrait.get(id=character_trait.id)
            assert updated_ct.value == trait.max_value - 1

    async def test_increase_trait_value_with_xp(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_campaign: Any,
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify purchasing a trait value increase with XP."""
        # Given a character with XP
        character_player_user = await user_factory(
            role=UserRole.PLAYER.value, company=session_company
        )
        character = await character_factory(
            company=session_company,
            user_player=character_player_user,
            user_creator=character_player_user,
            campaign=session_campaign,
        )
        trait = await Trait.filter(is_archived=False).first()
        character_trait = await character_trait_factory(value=0, trait=trait, character=character)
        user_svc = UserXPService()
        await user_svc.add_xp(character_player_user.id, character.campaign_id, 100)

        # When purchasing a trait value with XP
        response = await client.put(
            build_url(
                Characters.TRAIT_VALUE,
                company_id=session_company.id,
                user_id=character_player_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                character_trait_id=character_trait.id,
            ),
            headers=token_global_admin,
            json={"target_value": 1, "currency": "XP"},
        )

        # Then the response should succeed and XP should be deducted
        assert response.status_code == HTTP_200_OK
        updated_ct = await CharacterTrait.get(id=character_trait.id)
        assert updated_ct.value == 1
        campaign_experience = await user_svc.get_or_create_campaign_experience(
            character_player_user.id, character.campaign_id
        )
        assert campaign_experience.xp_current == 100 - trait.initial_cost
        assert campaign_experience.xp_total == 100

    async def test_increase_trait_value_with_xp_as_storyteller(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_campaign: Any,
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify a storyteller can purchase trait values with XP for any character."""
        # Given a storyteller and a character owned by another player
        storyteller_user = await user_factory(
            role=UserRole.STORYTELLER.value, company=session_company, username="Storyteller User"
        )
        character_player_user = await user_factory(
            role=UserRole.PLAYER.value, company=session_company
        )
        character = await character_factory(
            company=session_company,
            user_player=character_player_user,
            user_creator=character_player_user,
            campaign=session_campaign,
        )
        trait = await Trait.filter(is_archived=False).first()
        character_trait = await character_trait_factory(value=0, trait=trait, character=character)
        user_svc = UserXPService()
        await user_svc.add_xp(character_player_user.id, character.campaign_id, 100)

        # When the storyteller purchases a trait value with XP
        response = await client.put(
            build_url(
                Characters.TRAIT_VALUE,
                company_id=session_company.id,
                user_id=storyteller_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                character_trait_id=character_trait.id,
            ),
            headers=token_global_admin,
            json={"target_value": 1, "currency": "XP"},
        )

        # Then the response should succeed
        assert response.status_code == HTTP_200_OK
        updated_ct = await CharacterTrait.get(id=character_trait.id)
        assert updated_ct.value == 1

    async def test_increase_trait_value_fail_as_non_owner_player(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_campaign: Any,
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify a player cannot modify traits on a character they don't own."""
        # Given a player trying to modify another player's character
        player_user = await user_factory(
            role=UserRole.PLAYER.value, company=session_company, username="Player User"
        )
        character_player_user = await user_factory(
            role=UserRole.PLAYER.value, company=session_company
        )
        character = await character_factory(
            company=session_company,
            user_player=character_player_user,
            user_creator=character_player_user,
            campaign=session_campaign,
        )
        trait = await Trait.filter(is_archived=False).first()
        character_trait = await character_trait_factory(value=0, trait=trait, character=character)
        user_svc = UserXPService()
        await user_svc.add_xp(character_player_user.id, character.campaign_id, 100)

        # When the non-owner player tries to modify the trait
        response = await client.put(
            build_url(
                Characters.TRAIT_VALUE,
                company_id=session_company.id,
                user_id=player_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                character_trait_id=character_trait.id,
            ),
            headers=token_global_admin,
            json={"target_value": 1, "currency": "XP"},
        )

        # Then the response should be forbidden
        assert response.status_code == HTTP_403_FORBIDDEN

    async def test_decrease_trait_value_with_xp_refund(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_campaign: Any,
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify refunding a trait value decrease with XP."""
        # Given a character with a trait at max value
        character_player_user = await user_factory(
            role=UserRole.PLAYER.value, company=session_company
        )
        character = await character_factory(
            company=session_company,
            user_player=character_player_user,
            user_creator=character_player_user,
            campaign=session_campaign,
        )
        trait = await Trait.filter(is_archived=False).first()
        character_trait = await character_trait_factory(
            value=trait.max_value, trait=trait, character=character
        )
        user_svc = UserXPService()
        await user_svc.add_xp(character_player_user.id, character.campaign_id, 100)

        # When refunding a trait value
        response = await client.put(
            build_url(
                Characters.TRAIT_VALUE,
                company_id=session_company.id,
                user_id=character_player_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                character_trait_id=character_trait.id,
            ),
            headers=token_global_admin,
            json={"target_value": trait.max_value - 1, "currency": "XP"},
        )

        # Then the response should succeed and XP should be refunded
        assert response.status_code == HTTP_200_OK
        updated_ct = await CharacterTrait.get(id=character_trait.id)
        assert updated_ct.value == trait.max_value - 1
        campaign_experience = await user_svc.get_or_create_campaign_experience(
            character_player_user.id, character.campaign_id
        )
        assert campaign_experience.xp_current == 100 + (trait.initial_cost * trait.max_value)
        assert campaign_experience.xp_total == 100

    async def test_increase_trait_value_with_starting_points(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_user: User,
        session_campaign: Any,
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify purchasing a trait value increase with starting points."""
        # Given a character with starting points
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            starting_points=100,
        )
        trait = await Trait.filter(is_archived=False).first()
        character_trait = await character_trait_factory(value=0, trait=trait, character=character)

        # When purchasing a trait value with starting points
        response = await client.put(
            build_url(
                Characters.TRAIT_VALUE,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                character_trait_id=character_trait.id,
            ),
            headers=token_global_admin,
            json={"target_value": 1, "currency": "STARTING_POINTS"},
        )

        # Then the response should succeed and starting points should be deducted
        assert response.status_code == HTTP_200_OK
        updated_ct = await CharacterTrait.get(id=character_trait.id)
        assert updated_ct.value == 1
        updated_character = await Character.get(id=character.id)
        assert updated_character.starting_points == 100 - trait.initial_cost

    async def test_decrease_trait_value_with_starting_points_refund(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_user: User,
        session_campaign: Any,
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify refunding a trait value decrease with starting points."""
        # Given a character with a trait at max value
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
            starting_points=100,
        )
        trait = await Trait.filter(is_archived=False).first()
        character_trait = await character_trait_factory(
            value=trait.max_value, trait=trait, character=character
        )

        # When refunding a trait value with starting points
        response = await client.put(
            build_url(
                Characters.TRAIT_VALUE,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                character_trait_id=character_trait.id,
            ),
            headers=token_global_admin,
            json={"target_value": trait.max_value - 1, "currency": "STARTING_POINTS"},
        )

        # Then the response should succeed and starting points should be refunded
        assert response.status_code == HTTP_200_OK
        updated_ct = await CharacterTrait.get(id=character_trait.id)
        assert updated_ct.value == trait.max_value - 1
        updated_character = await Character.get(id=character.id)
        assert updated_character.starting_points == 125


class TestGetValueOptions:
    """Test getting value options for a trait."""

    async def test_get_value_options(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_campaign: Any,
        user_factory: Callable[..., User],
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify getting value options returns correct structure."""
        # Given a character with XP and starting points
        character_player_user = await user_factory(
            role=UserRole.PLAYER.value, company=session_company
        )
        character = await character_factory(
            company=session_company,
            user_player=character_player_user,
            user_creator=character_player_user,
            campaign=session_campaign,
            starting_points=50,
        )
        trait = await Trait.filter(is_archived=False).first()
        character_trait = await character_trait_factory(value=2, trait=trait, character=character)
        user_svc = UserXPService()
        await user_svc.add_xp(character_player_user.id, character.campaign_id, 100)

        # When getting value options
        response = await client.get(
            build_url(
                Characters.TRAIT_VALUE_OPTIONS,
                company_id=session_company.id,
                user_id=character_player_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
                character_trait_id=character_trait.id,
            ),
            headers=token_global_admin,
        )

        # Then the response should contain the correct structure
        assert response.status_code == HTTP_200_OK
        result = response.json()
        assert result["current_value"] == 2
        assert result["trait"]["id"] == str(trait.id)
        assert result["xp_current"] == 100
        assert result["starting_points_current"] == 50
        assert "options" in result

        # Current value should not be in options
        assert "2" not in result["options"]

        # Should have upgrade options (if not at max)
        if trait.max_value > 2:
            assert "3" in result["options"]
            assert result["options"]["3"]["direction"] == "increase"

        # Should have downgrade options (if not at min)
        if trait.min_value < 2:
            assert "1" in result["options"]
            assert result["options"]["1"]["direction"] == "decrease"


class TestBulkAssignTraitsToCharacter:
    """Test the bulk assign traits endpoint."""

    async def test_bulk_assign_mixed_outcomes(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_user: User,
        session_campaign: Any,
        character_factory: Callable[..., Character],
        character_trait_factory: Callable[..., CharacterTrait],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify bulk assign returns succeeded and failed lists with mixed outcomes."""
        # Given a character with one existing trait
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        existing_ct = await character_trait_factory(character=character)
        existing_trait_id = existing_ct.trait_id

        # And two unused traits
        unused_traits = await Trait.filter(is_archived=False).exclude(id=existing_trait_id).limit(2)
        valid_trait_1 = unused_traits[0]
        valid_trait_2 = unused_traits[1]

        # When bulk assigning: 2 valid + 1 duplicate
        response = await client.post(
            build_url(
                Characters.TRAIT_BULK_ASSIGN,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
            ),
            headers=token_global_admin,
            json=[
                {
                    "trait_id": str(valid_trait_1.id),
                    "value": 1,
                    "currency": TraitModifyCurrency.NO_COST.value,
                },
                {
                    "trait_id": str(existing_trait_id),
                    "value": 1,
                    "currency": TraitModifyCurrency.NO_COST.value,
                },
                {
                    "trait_id": str(valid_trait_2.id),
                    "value": 1,
                    "currency": TraitModifyCurrency.NO_COST.value,
                },
            ],
        )

        # Then response is 200 with correct succeeded/failed
        assert response.status_code == HTTP_200_OK
        body = response.json()
        assert len(body["succeeded"]) == 2
        assert len(body["failed"]) == 1
        assert body["failed"][0]["trait_id"] == str(existing_trait_id)

        # And succeeded traits are persisted in the database
        for item in body["succeeded"]:
            ct = (
                await CharacterTrait.filter(id=item["character_trait"]["id"])
                .prefetch_related(
                    "trait", "trait__category", "trait__subcategory", "trait__sheet_section"
                )
                .first()
            )
            assert ct is not None
            assert ct.value == 1

    async def test_exceeds_max_batch_size(
        self,
        client: AsyncClient,
        build_url: Callable[..., str],
        session_company: Company,
        session_global_admin: Any,
        session_user: User,
        session_campaign: Any,
        character_factory: Callable[..., Character],
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify request with more than 200 items returns 400."""
        # Given a batch of 201 items (using a fake trait_id repeated)
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        fake_id = str(uuid4())
        items = [
            {"trait_id": fake_id, "value": 1, "currency": TraitModifyCurrency.NO_COST.value}
            for _ in range(201)
        ]

        # When sending the oversized batch
        response = await client.post(
            build_url(
                Characters.TRAIT_BULK_ASSIGN,
                company_id=session_company.id,
                user_id=session_user.id,
                campaign_id=character.campaign_id,
                character_id=character.id,
            ),
            headers=token_global_admin,
            json=items,
        )

        # Then the request is rejected
        assert response.status_code == HTTP_400_BAD_REQUEST
