"""Test the character trait service."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY

import pytest
from beanie import PydanticObjectId
from beanie.operators import In, Not

from vapi.constants import (
    CharacterClass,
    PermissionsFreeTraitChanges,
    TraitModifyCurrency,
    UserRole,
)
from vapi.db.models import (
    Campaign,
    Character,
    CharacterTrait,
    Company,
    Trait,
    TraitCategory,
    User,
)
from vapi.domain.controllers.character_trait.dto import (
    CharacterTraitAddConstant,
    CharacterTraitCreateCustomDTO,
)
from vapi.domain.services import CharacterTraitService, GetModelByIdValidationService
from vapi.lib.exceptions import (
    ConflictError,
    NotEnoughXPError,
    PermissionDeniedError,
    ValidationError,
)
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from collections.abc import Callable


pytestmark = pytest.mark.anyio


@pytest.fixture
async def get_company_user_character(
    company_factory: Callable[[dict[str, ...]], Company],
    user_factory: Callable[[dict[str, ...]], User],
    character_factory: Callable[[dict[str, ...]], Character],
) -> tuple[Company, User, Character]:
    """Create a company, user, and character that will pass all guard checks."""
    company = await company_factory()
    user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
    character = await character_factory(company_id=company.id, user_player_id=user.id)

    yield company, user, character

    # Cleanup
    await character.delete()
    await user.delete()
    await company.delete()


class TestListCharacterTraits:
    """Test the list_character_traits method."""

    async def test_list_character_traits(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify that the list_character_traits method works."""
        # Given a character with traits
        await CharacterTrait.delete_all()
        character = await character_factory()
        trait_ids = []
        for _ in range(8):
            trait = await Trait.find_one(Trait.is_archived == False, Not(In(Trait.id, trait_ids)))
            trait_ids.append(trait.id)
            await character_trait_factory(character_id=character.id, trait=trait, value=1)

        # When we list the traits
        service = CharacterTraitService()
        count, traits = await service.list_character_traits(character)

        # Then the traits should be listed correctly
        assert count == 8
        assert len(traits) == 8
        assert isinstance(traits[0], CharacterTrait)

    async def test_list_character_traits_no_traits(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify that the list_character_traits method works."""
        # Given a character with traits
        await CharacterTrait.delete_all()
        character = await character_factory()

        # When we list the traits
        service = CharacterTraitService()
        count, traits = await service.list_character_traits(character)

        # Then the traits should be listed correctly
        assert count == 0
        assert len(traits) == 0

    async def test_list_character_traits_skip_limit(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        debug: Callable[[...], None],
    ) -> None:
        """Verify that the list_character_traits method works."""
        # Given a character with traits
        await CharacterTrait.delete_all()
        character = await character_factory()
        trait_ids = []
        created_character_traits = []
        for _ in range(8):
            trait = await Trait.find_one(Trait.is_archived == False, Not(In(Trait.id, trait_ids)))
            trait_ids.append(trait.id)
            character_trait = await character_trait_factory(
                character_id=character.id, trait=trait, value=1
            )
            created_character_traits.append(character_trait)

        sorted_created_character_traits = sorted(
            created_character_traits[3:5], key=lambda x: x.trait.parent_category_id
        )

        # When we list the traits
        service = CharacterTraitService()
        count, traits = await service.list_character_traits(character, limit=2, offset=3)

        # Then the traits should be listed correctly
        assert count == 8
        assert len(traits) == 2
        assert isinstance(traits[0], CharacterTrait)
        assert sorted_created_character_traits == traits

    async def test_list_character_traits_filter_by_parent_category_id(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify that the list_character_traits method works."""
        # Given a character with traits
        await CharacterTrait.delete_all()
        character = await character_factory()
        category1 = await TraitCategory.find_one(TraitCategory.is_archived == False)
        category2 = await TraitCategory.find_one(
            TraitCategory.is_archived == False, TraitCategory.id != category1.id
        )

        trait_ids = []
        for _ in range(3):
            trait = await Trait.find_one(
                Trait.is_archived == False,
                Not(In(Trait.id, trait_ids)),
                Trait.parent_category_id == category1.id,
            )
            trait_ids.append(trait.id)
            await character_trait_factory(character_id=character.id, trait=trait, value=1)
        for _ in range(3):
            trait = await Trait.find_one(
                Trait.is_archived == False,
                Not(In(Trait.id, trait_ids)),
                Trait.parent_category_id == category2.id,
            )
            trait_ids.append(trait.id)
            await character_trait_factory(character_id=character.id, trait=trait, value=1)

        # When we list the traits
        service = CharacterTraitService()
        count, traits = await service.list_character_traits(
            character, parent_category_id=category1.id
        )

        # Then the traits should be listed correctly
        assert count == 3
        assert len(traits) == 3
        assert isinstance(traits[0], CharacterTrait)
        for trait in traits:
            assert trait.trait.parent_category_id == category1.id

    async def test_list_character_traits_filter_by_is_rollable(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify that filtering by is_rollable returns only rollable traits."""
        # Given a character with both rollable and non-rollable traits
        await CharacterTrait.delete_all()
        character = await character_factory()

        trait_ids: list[PydanticObjectId] = []
        rollable_trait = await Trait.find_one(
            Trait.is_archived == False,
            Trait.is_rollable == True,
            Not(In(Trait.id, trait_ids)),
        )
        trait_ids.append(rollable_trait.id)
        await character_trait_factory(character_id=character.id, trait=rollable_trait, value=1)

        non_rollable_trait = await Trait.find_one(
            Trait.is_archived == False,
            Trait.is_rollable == False,
            Not(In(Trait.id, trait_ids)),
        )
        trait_ids.append(non_rollable_trait.id)
        await character_trait_factory(character_id=character.id, trait=non_rollable_trait, value=1)

        # When we list the traits filtered by is_rollable
        service = CharacterTraitService()
        count, traits = await service.list_character_traits(character, is_rollable=True)

        # Then only rollable traits should be returned
        assert count == 1
        assert len(traits) == 1
        assert traits[0].trait.is_rollable is True

    async def test_list_character_traits_filter_by_not_rollable(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify that is_rollable=False returns only non-rollable traits."""
        # Given a character with both rollable and non-rollable traits
        await CharacterTrait.delete_all()
        character = await character_factory()

        trait_ids: list[PydanticObjectId] = []
        rollable_trait = await Trait.find_one(
            Trait.is_archived == False,
            Trait.is_rollable == True,
            Not(In(Trait.id, trait_ids)),
        )
        trait_ids.append(rollable_trait.id)
        await character_trait_factory(character_id=character.id, trait=rollable_trait, value=1)

        non_rollable_trait = await Trait.find_one(
            Trait.is_archived == False,
            Trait.is_rollable == False,
            Not(In(Trait.id, trait_ids)),
        )
        trait_ids.append(non_rollable_trait.id)
        await character_trait_factory(character_id=character.id, trait=non_rollable_trait, value=1)

        # When we list the traits filtered by is_rollable=False
        service = CharacterTraitService()
        count, traits = await service.list_character_traits(character, is_rollable=False)

        # Then only non-rollable traits should be returned
        assert count == 1
        assert len(traits) == 1
        assert traits[0].trait.is_rollable is False

    async def test_list_character_traits_is_rollable_none_returns_all(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify that is_rollable=None does not filter traits."""
        # Given a character with both rollable and non-rollable traits
        await CharacterTrait.delete_all()
        character = await character_factory()

        trait_ids: list[PydanticObjectId] = []
        rollable_trait = await Trait.find_one(
            Trait.is_archived == False,
            Trait.is_rollable == True,
            Not(In(Trait.id, trait_ids)),
        )
        trait_ids.append(rollable_trait.id)
        await character_trait_factory(character_id=character.id, trait=rollable_trait, value=1)

        non_rollable_trait = await Trait.find_one(
            Trait.is_archived == False,
            Trait.is_rollable == False,
            Not(In(Trait.id, trait_ids)),
        )
        trait_ids.append(non_rollable_trait.id)
        await character_trait_factory(character_id=character.id, trait=non_rollable_trait, value=1)

        # When we list the traits without the is_rollable filter
        service = CharacterTraitService()
        count, traits = await service.list_character_traits(character, is_rollable=None)

        # Then all traits should be returned
        assert count == 2
        assert len(traits) == 2


class TestGuardPermissionsFreeTraitChanges:
    """Test the guard_permissions_free_trait_changes method."""

    @pytest.mark.parametrize(
        ("permission_setting", "user_role", "is_new_character", "will_pass"),
        [
            (PermissionsFreeTraitChanges.UNRESTRICTED, UserRole.ADMIN, False, True),
            (PermissionsFreeTraitChanges.UNRESTRICTED, UserRole.ADMIN, True, True),
            (PermissionsFreeTraitChanges.UNRESTRICTED, UserRole.STORYTELLER, False, True),
            (PermissionsFreeTraitChanges.UNRESTRICTED, UserRole.STORYTELLER, True, True),
            (PermissionsFreeTraitChanges.UNRESTRICTED, UserRole.PLAYER, True, True),
            (PermissionsFreeTraitChanges.UNRESTRICTED, UserRole.PLAYER, False, True),
            (PermissionsFreeTraitChanges.STORYTELLER, UserRole.ADMIN, False, True),
            (PermissionsFreeTraitChanges.STORYTELLER, UserRole.ADMIN, True, True),
            (PermissionsFreeTraitChanges.STORYTELLER, UserRole.STORYTELLER, False, True),
            (PermissionsFreeTraitChanges.STORYTELLER, UserRole.STORYTELLER, True, True),
            (PermissionsFreeTraitChanges.STORYTELLER, UserRole.PLAYER, True, False),
            (PermissionsFreeTraitChanges.STORYTELLER, UserRole.PLAYER, False, False),
            (PermissionsFreeTraitChanges.WITHIN_24_HOURS, UserRole.ADMIN, False, True),
            (PermissionsFreeTraitChanges.WITHIN_24_HOURS, UserRole.ADMIN, True, True),
            (PermissionsFreeTraitChanges.WITHIN_24_HOURS, UserRole.STORYTELLER, False, True),
            (PermissionsFreeTraitChanges.WITHIN_24_HOURS, UserRole.STORYTELLER, True, True),
            (PermissionsFreeTraitChanges.WITHIN_24_HOURS, UserRole.PLAYER, True, True),
            (PermissionsFreeTraitChanges.WITHIN_24_HOURS, UserRole.PLAYER, False, False),
        ],
    )
    async def test_guard_permissions_free_trait_changes(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        user_factory: Callable[[dict[str, ...]], User],
        company_factory: Callable[[dict[str, ...]], Company],
        user_role: UserRole,
        is_new_character: bool,
        permission_setting: PermissionsFreeTraitChanges,
        will_pass: bool,
    ) -> None:
        """Verify that the guard_permissions_free_trait_changes method works for an unrestricted company."""
        # Given a company with an unrestricted permission free trait changes and a user and character
        service = CharacterTraitService()
        company = await company_factory()
        company.settings.permission_free_trait_changes = permission_setting
        await company.save()
        user = await user_factory(company_id=company.id, role=user_role)
        character = await character_factory(
            company_id=company.id,
            date_created=time_now() - timedelta(hours=12)
            if is_new_character
            else time_now() - timedelta(hours=45),
        )

        # When we guard the permissions free trait changes
        if will_pass:
            result = service._guard_permissions_free_trait_changes(company, character, user)
            assert result is True
        else:
            with pytest.raises(PermissionDeniedError):
                service._guard_permissions_free_trait_changes(company, character, user)


class TestGuardUserCanManageCharacter:
    """Test the guard_user_can_manage_character method."""

    async def testguard_user_can_manage_character_storyteller(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        user_factory: Callable[[dict[str, ...]], User],
    ) -> None:
        """Verify that the user_can_manage_character method works for a storyteller."""
        # Given a character owned by a player and a storyteller user
        service = CharacterTraitService()
        character_owner = await user_factory(role=UserRole.PLAYER)
        character = await character_factory(
            user_player_id=character_owner.id,
            user_creator_id=character_owner.id,
        )
        storyteller_user = await user_factory(role=UserRole.STORYTELLER)

        # When we guard the user can manage the character
        result = service.guard_user_can_manage_character(character, storyteller_user)

        # Then the result should be True
        assert result is True

    async def testguard_user_can_manage_character_player(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        user_factory: Callable[[dict[str, ...]], User],
    ) -> None:
        """Verify that the user_can_manage_character method works for a storyteller."""
        # Given a character owned by a player and a player user
        service = CharacterTraitService()
        character_owner = await user_factory(role=UserRole.PLAYER)
        character = await character_factory(
            user_player_id=character_owner.id,
            user_creator_id=character_owner.id,
        )

        # When we guard the user can manage the character
        result = service.guard_user_can_manage_character(character, character_owner)

        # Then the result should be True
        assert result is True

    async def testguard_user_can_manage_character_admin(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        user_factory: Callable[[dict[str, ...]], User],
    ) -> None:
        """Verify that the user_can_manage_character method works for an admin."""
        service = CharacterTraitService()
        character_owner = await user_factory(role=UserRole.PLAYER)
        character = await character_factory(
            user_player_id=character_owner.id,
            user_creator_id=character_owner.id,
        )
        admin_user = await user_factory(role=UserRole.ADMIN)

        # When we guard the user can manage the character
        result = service.guard_user_can_manage_character(character, admin_user)

        # Then the result should be True
        assert result is True

    async def testguard_user_can_manage_character_not_owner(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        user_factory: Callable[[dict[str, ...]], User],
    ) -> None:
        """Verify that the user_can_manage_character method fails for a user who is not the owner of the character."""
        # Given a character owned by a player and a player user who is not the owner
        service = CharacterTraitService()
        character_owner = await user_factory(role=UserRole.PLAYER)
        character = await character_factory(
            user_player_id=character_owner.id,
            user_creator_id=character_owner.id,
        )
        not_owner_user = await user_factory(role=UserRole.PLAYER)

        # When we guard the user can manage the character
        # Then a PermissionDeniedError should be raised
        with pytest.raises(PermissionDeniedError, match="User does not own this character"):
            service.guard_user_can_manage_character(character, not_owner_user)


class TestGuardIsSafeIncreaseDecrease:
    """Test the the guards for trait value increase and decrease."""

    async def test_guard_is_safe_increase(
        self, character_trait_factory: Callable[[dict[str, ...]], CharacterTrait]
    ) -> None:
        """Verify that the is_safe_increase method works."""
        service = CharacterTraitService()
        character_trait = await character_trait_factory(value=1)
        service._guard_is_safe_increase(character_trait, 1)

        # Then the trait value should be increased
        await character_trait.sync()
        assert True  # no exception raised

    async def test_guard_is_safe_increase_over_max_value(
        self, character_trait_factory: Callable[[dict[str, ...]], CharacterTrait]
    ) -> None:
        """Verify that the is_safe_increase method works."""
        service = CharacterTraitService()
        trait = await Trait.find_one(Trait.is_archived == False)
        character_trait = await character_trait_factory(value=trait.max_value, trait=trait)
        with pytest.raises(ValidationError, match="Trait can not be raised above max value of"):
            service._guard_is_safe_increase(character_trait, 1)

        # cleanup non-constant trait
        await trait.delete()

    async def test_guard_is_safe_decrease(
        self, character_trait_factory: Callable[[dict[str, ...]], CharacterTrait]
    ) -> None:
        """Verify that the is_safe_decrease method works."""
        service = CharacterTraitService()
        trait = await Trait.find_one(Trait.is_archived == False)
        character_trait = await character_trait_factory(value=trait.max_value, trait=trait)
        service._guard_is_safe_decrease(character_trait, 1)
        assert True  # no exception raised

    async def test_guard_is_safe_decrease_below_min_value(
        self, character_trait_factory: Callable[[dict[str, ...]], CharacterTrait]
    ) -> None:
        """Verify that the is_safe_decrease method works."""
        service = CharacterTraitService()
        trait = await Trait.find_one(Trait.is_archived == False)
        character_trait = await character_trait_factory(value=trait.min_value, trait=trait)
        with pytest.raises(ValidationError, match="Trait can not be lowered below min value of"):
            service._guard_is_safe_decrease(character_trait, 1)

    @pytest.mark.parametrize(
        ("current_value", "initial_cost", "upgrade_cost", "increase_by", "expected"),
        [
            (4, 1, 1, 1, 5),
            (0, 1, 2, 1, 1),
            (1, 1, 2, 1, 4),
            (0, 1, 2, 2, 5),
            (1, 1, 2, 2, 10),
            (0, 1, 2, 3, 11),
        ],
    )
    async def test_calculate_upgrade_cost_initial_cost(
        self,
        initial_cost: int,
        upgrade_cost: int,
        increase_by: int,
        expected: int,
        current_value: int,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify that the cost to upgrade is correct for the initial cost.

        The max value of the trait is always set to 5
        """
        service = CharacterTraitService()
        trait = await trait_factory(
            initial_cost=initial_cost, upgrade_cost=upgrade_cost, max_value=5, is_custom=True
        )

        character_trait = await character_trait_factory(
            character_id=PydanticObjectId(),
            trait=trait,
            value=current_value,
        )
        assert await service.calculate_upgrade_cost(character_trait, increase_by) == expected

    async def test_calculate_upgrade_cost_over_max_value(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify that a validation error is raised if the trait is raised above the max value."""
        service = CharacterTraitService()
        trait = await trait_factory(max_value=5, is_custom=True)
        character_trait = await character_trait_factory(
            character_id=PydanticObjectId(),
            trait=trait,
            value=4,
        )

        with pytest.raises(ValidationError):
            await service.calculate_upgrade_cost(character_trait, 2)


class TestIsFlawTrait:
    """Test the _is_flaw_trait method."""

    async def test_flaw_trait_returns_true(
        self,
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify flaw traits are correctly identified."""
        # Given a trait in the "Flaws" parent category
        flaws_category = await TraitCategory.find_one(TraitCategory.name == "Flaws")
        flaw_trait = await trait_factory(parent_category_id=flaws_category.id)
        character_trait = await character_trait_factory(trait=flaw_trait, value=1)

        # When we check if it's a flaw
        service = CharacterTraitService()
        result = await service._is_flaw_trait(character_trait)

        # Then it should return True
        assert result is True

    async def test_non_flaw_trait_returns_false(
        self,
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify non-flaw traits are correctly identified."""
        # Given a regular trait
        character_trait = await character_trait_factory(value=1)

        # When we check if it's a flaw
        service = CharacterTraitService()
        result = await service._is_flaw_trait(character_trait)

        # Then it should return False
        assert result is False

    async def test_non_flaw_category_returns_false(
        self,
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify traits in a non-Flaws category are not flaws."""
        # Given a trait in a category that is not "Flaws"
        non_flaw_category = await TraitCategory.find_one(TraitCategory.name != "Flaws")
        trait = await trait_factory(parent_category_id=non_flaw_category.id)
        character_trait = await character_trait_factory(trait=trait, value=1)

        # When we check if it's a flaw
        service = CharacterTraitService()
        result = await service._is_flaw_trait(character_trait)

        # Then it should return False
        assert result is False


class TestCostForDot:
    """Test the _cost_for_dot helper method."""

    async def test_cost_for_first_dot_uses_initial_cost(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify first dot uses initial_cost."""
        # Given a trait with initial_cost=3, upgrade_cost=5
        service = CharacterTraitService()
        trait = await trait_factory(
            initial_cost=3, upgrade_cost=5, max_value=5, min_value=0, is_custom=True
        )
        character_trait = await character_trait_factory(trait=trait, value=0)
        await character_trait.fetch_all_links()

        # When we calculate cost for dot 1
        result = service._cost_for_dot(character_trait, 1)

        # Then it uses initial_cost
        assert result == 3

    async def test_cost_for_higher_dot_uses_upgrade_cost(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify dots above 1 use dot_value * upgrade_cost."""
        # Given a trait with initial_cost=3, upgrade_cost=5
        service = CharacterTraitService()
        trait = await trait_factory(
            initial_cost=3, upgrade_cost=5, max_value=5, min_value=0, is_custom=True
        )
        character_trait = await character_trait_factory(trait=trait, value=0)
        await character_trait.fetch_all_links()

        # When we calculate cost for dot 3
        result = service._cost_for_dot(character_trait, 3)

        # Then it uses dot_value * upgrade_cost
        assert result == 15


class TestCountCategoryTraits:
    """Test the _count_category_traits method."""

    async def test_count_with_no_traits_in_category(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
    ) -> None:
        """Verify count is zero when character has no traits in the category."""
        # Given a character with no traits
        await CharacterTrait.delete_all()
        character = await character_factory()
        category = await TraitCategory.find_one(TraitCategory.is_archived == False)

        # When counting traits in the category
        service = CharacterTraitService()
        result = await service._count_category_traits(character.id, category.id)

        # Then the count is zero
        assert result == 0

    async def test_count_with_traits_in_category(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify count reflects traits with value > 0 in the given category."""
        # Given a character with 2 gift traits
        await CharacterTrait.delete_all()
        character = await character_factory()

        gift_traits = await Trait.find(
            Trait.gift_attributes != None,
            Trait.is_archived == False,
        ).to_list(2)
        if len(gift_traits) < 2:
            pytest.skip("Not enough gift traits in database")

        gifts_category_id = gift_traits[0].parent_category_id
        for gift_trait in gift_traits:
            await character_trait_factory(character_id=character.id, trait=gift_trait, value=1)

        # When counting traits in the gifts category
        service = CharacterTraitService()
        result = await service._count_category_traits(character.id, gifts_category_id)

        # Then the count is 2
        assert result == 2

    async def test_count_excludes_zero_value_traits(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify traits with value=0 are excluded from count."""
        # Given a character with one active and one inactive gift
        await CharacterTrait.delete_all()
        character = await character_factory()

        gift_traits = await Trait.find(
            Trait.gift_attributes != None,
            Trait.is_archived == False,
        ).to_list(2)
        if len(gift_traits) < 2:
            pytest.skip("Not enough gift traits in database")

        gifts_category_id = gift_traits[0].parent_category_id
        await character_trait_factory(character_id=character.id, trait=gift_traits[0], value=1)
        await character_trait_factory(character_id=character.id, trait=gift_traits[1], value=0)

        # When counting traits in the gifts category
        service = CharacterTraitService()
        result = await service._count_category_traits(character.id, gifts_category_id)

        # Then only the active trait is counted
        assert result == 1

    async def test_count_excludes_other_categories(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify traits from other categories are excluded from count."""
        # Given a character with a gift and a non-gift trait
        await CharacterTrait.delete_all()
        character = await character_factory()

        gift_trait = await Trait.find_one(
            Trait.gift_attributes != None,
            Trait.is_archived == False,
        )
        if gift_trait is None:
            pytest.skip("No gift trait in database")

        gifts_category_id = gift_trait.parent_category_id
        await character_trait_factory(character_id=character.id, trait=gift_trait, value=1)

        non_gift_trait = await Trait.find_one(
            Trait.parent_category_id != gifts_category_id,
            Trait.is_archived == False,
        )
        if non_gift_trait is None:
            pytest.skip("No non-gift trait in database")

        await character_trait_factory(character_id=character.id, trait=non_gift_trait, value=3)

        # When counting traits in the gifts category
        service = CharacterTraitService()
        result = await service._count_category_traits(character.id, gifts_category_id)

        # Then only the gift is counted
        assert result == 1


class TestCalculateAllUpgradeCosts:
    """Test the calculate_all_upgrade_costs method."""

    async def test_returns_empty_dict_at_max_value(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify empty dictionary returned when trait is at max value."""
        # Given a trait at its max value
        service = CharacterTraitService()
        trait = await trait_factory(max_value=5, min_value=0, is_custom=True)
        character_trait = await character_trait_factory(
            character_id=PydanticObjectId(),
            trait=trait,
            value=5,
        )

        # When we calculate all upgrade costs
        result = await service.calculate_all_upgrade_costs(character_trait)

        # Then the result should be an empty dictionary
        assert result == {}

    async def test_returns_single_cost_one_below_max(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify single cost returned when trait is one below max value."""
        # Given a trait one below max value (value=4, max=5)
        service = CharacterTraitService()
        trait = await trait_factory(
            initial_cost=1, upgrade_cost=2, max_value=5, min_value=0, is_custom=True
        )
        character_trait = await character_trait_factory(
            character_id=PydanticObjectId(),
            trait=trait,
            value=4,
        )

        # When we calculate all upgrade costs
        result = await service.calculate_all_upgrade_costs(character_trait)

        # Then we should get exactly one cost entry with key 1 (increase by 1 dot)
        assert len(result) == 1
        assert "1" in result
        # Cost to go from 4 to 5: 5 * upgrade_cost = 5 * 2 = 10
        assert result["1"] == 10

    async def test_returns_costs_for_multiple_levels(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify costs returned for each possible number of dots to increase."""
        # Given a trait with value 3 and max_value 5
        service = CharacterTraitService()
        trait = await trait_factory(
            initial_cost=1, upgrade_cost=2, max_value=5, min_value=0, is_custom=True
        )
        character_trait = await character_trait_factory(
            character_id=PydanticObjectId(),
            trait=trait,
            value=3,
        )

        # When we calculate all upgrade costs
        result = await service.calculate_all_upgrade_costs(character_trait)

        # Then keys should be 1 and 2 (can increase by 1 or 2 dots)
        assert set(result.keys()) == {"1", "2"}
        # Cost to increase by 1 (3→4): 4 * 2 = 8
        assert result["1"] == 8
        # Cost to increase by 2 (3→5): (4 * 2) + (5 * 2) = 8 + 10 = 18
        assert result["2"] == 18

    async def test_cost_values_are_positive_integers(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify all cost values are positive integers."""
        # Given a trait with room to upgrade
        service = CharacterTraitService()
        trait = await trait_factory(
            initial_cost=1, upgrade_cost=2, max_value=5, min_value=0, is_custom=True
        )
        character_trait = await character_trait_factory(
            character_id=PydanticObjectId(),
            trait=trait,
            value=2,
        )

        # When we calculate all upgrade costs
        result = await service.calculate_all_upgrade_costs(character_trait)

        # Then all values should be positive integers
        for cost in result.values():
            assert isinstance(cost, int)
            assert cost > 0


class TestCalculateAllDowngradeSavings:
    """Test the calculate_all_downgrade_savings method."""

    async def test_returns_delete_but_no_other_savings_at_min_value(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify only delete savings returned when trait is at min value."""
        # Given a trait at its min value
        service = CharacterTraitService()
        trait = await trait_factory(max_value=5, min_value=0, is_custom=True)
        character_trait = await character_trait_factory(
            character_id=PydanticObjectId(),
            trait=trait,
            value=0,
        )

        # When we calculate all downgrade savings
        result = await service.calculate_all_downgrade_savings(character_trait)

        # Then the result should be an empty dictionary
        assert result == {"DELETE": 0}

    async def test_returns_single_savings_one_above_min(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify single savings returned when trait is one above min value."""
        # Given a trait one above min value (value=1, min=0)
        service = CharacterTraitService()
        trait = await trait_factory(
            initial_cost=1, upgrade_cost=2, max_value=5, min_value=0, is_custom=True
        )
        character_trait = await character_trait_factory(
            character_id=PydanticObjectId(),
            trait=trait,
            value=1,
        )

        # When we calculate all downgrade savings
        result = await service.calculate_all_downgrade_savings(character_trait)

        # Then we should get exactly one savings entry with key 1 (decrease by 1 dot)
        assert len(result) == 2
        assert "1" in result
        # Savings to go from 1 to 0: initial_cost = 1
        assert result["1"] == 1
        assert result["DELETE"] == 1

    async def test_returns_savings_for_multiple_levels(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify savings returned for each possible number of dots to decrease."""
        # Given a trait with value 3 and min_value 0
        service = CharacterTraitService()
        trait = await trait_factory(
            initial_cost=1, upgrade_cost=2, max_value=5, min_value=0, is_custom=True
        )
        character_trait = await character_trait_factory(
            character_id=PydanticObjectId(),
            trait=trait,
            value=3,
        )

        # When we calculate all downgrade savings
        result = await service.calculate_all_downgrade_savings(character_trait)

        # Then keys should be 1, 2, and 3 (can decrease by 1, 2, or 3 dots)
        assert set(result.keys()) == {"1", "2", "3", "DELETE"}
        # Savings to decrease by 1 (3→2): 3 * upgrade_cost = 3 * 2 = 6
        assert result["1"] == 6
        # Savings to decrease by 2 (3→1): (3 * 2) + (2 * 2) = 6 + 4 = 10
        assert result["2"] == 10
        # Savings to decrease by 3 (3→0): (3 * 2) + (2 * 2) + initial_cost = 6 + 4 + 1 = 11
        assert result["3"] == 11
        assert result["DELETE"] == 11

    async def test_savings_values_are_positive_integers(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify all savings values are positive integers."""
        # Given a trait with room to downgrade
        service = CharacterTraitService()
        trait = await trait_factory(
            initial_cost=1, upgrade_cost=2, max_value=5, min_value=0, is_custom=True
        )
        character_trait = await character_trait_factory(
            character_id=PydanticObjectId(),
            trait=trait,
            value=3,
        )

        # When we calculate all downgrade savings
        result = await service.calculate_all_downgrade_savings(character_trait)

        # Then all values should be positive integers
        for savings in result.values():
            assert isinstance(savings, int)
            assert savings > 0


class TestCountBasedUpgradeCost:
    """Test upgrade cost calculation for count-based traits."""

    async def test_first_gift_costs_2(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        company_factory: Callable[[dict[str, ...]], Company],
        user_factory: Callable[[dict[str, ...]], User],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify first gift costs 2 (1 * 2)."""
        # Given a character with no existing gifts
        company = await company_factory()
        user = await user_factory(company_id=company.id)
        character = await character_factory(
            company_id=company.id, user_player_id=user.id, character_class=CharacterClass.WEREWOLF
        )
        service = CharacterTraitService()

        gift_trait = await Trait.find_one(
            Trait.count_based_cost_multiplier == 2,
            Trait.is_archived == False,
        )
        if gift_trait is None:
            pytest.skip("No trait with count_based_cost_multiplier=2 in database")

        character_trait = await character_trait_factory(
            character_id=character.id, trait=gift_trait, value=0
        )

        # When calculating upgrade cost
        cost = await service.calculate_upgrade_cost(character_trait, 1)

        # Then cost is 2 (1st trait: 1 * 2)
        assert cost == 2

    async def test_fourth_gift_costs_8(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        company_factory: Callable[[dict[str, ...]], Company],
        user_factory: Callable[[dict[str, ...]], User],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify fourth gift costs 8 (4 * 2)."""
        # Given a character with 3 existing gifts
        company = await company_factory()
        user = await user_factory(company_id=company.id)
        character = await character_factory(
            company_id=company.id, user_player_id=user.id, character_class=CharacterClass.WEREWOLF
        )
        service = CharacterTraitService()

        gift_traits = await Trait.find(
            Trait.count_based_cost_multiplier == 2,
            Trait.is_archived == False,
        ).to_list(4)
        if len(gift_traits) < 4:
            pytest.skip("Not enough traits with count_based_cost_multiplier=2 in database")

        # Add 3 existing gifts with value=1
        for i in range(3):
            await character_trait_factory(character_id=character.id, trait=gift_traits[i], value=1)

        # Create the 4th gift at value=0 (about to be purchased)
        character_trait = await character_trait_factory(
            character_id=character.id, trait=gift_traits[3], value=0
        )

        # When calculating upgrade cost
        cost = await service.calculate_upgrade_cost(character_trait, 1)

        # Then cost is 8 (4th trait: 4 * 2)
        assert cost == 8

    async def test_ritual_first_costs_3(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        company_factory: Callable[[dict[str, ...]], Company],
        user_factory: Callable[[dict[str, ...]], User],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify first ritual costs 3 (1 * 3)."""
        # Given a character with no existing rituals
        company = await company_factory()
        user = await user_factory(company_id=company.id)
        character = await character_factory(company_id=company.id, user_player_id=user.id)
        service = CharacterTraitService()

        ritual_trait = await Trait.find_one(
            Trait.count_based_cost_multiplier == 3,
            Trait.is_archived == False,
        )
        if ritual_trait is None:
            pytest.skip("No trait with count_based_cost_multiplier=3 in database")

        character_trait = await character_trait_factory(
            character_id=character.id, trait=ritual_trait, value=0
        )

        # When calculating upgrade cost
        cost = await service.calculate_upgrade_cost(character_trait, 1)

        # Then cost is 3 (1st trait: 1 * 3)
        assert cost == 3

    async def test_ritual_third_costs_9(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        company_factory: Callable[[dict[str, ...]], Company],
        user_factory: Callable[[dict[str, ...]], User],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify third ritual costs 9 (3 * 3)."""
        # Given a character with 2 existing rituals in the same category
        company = await company_factory()
        user = await user_factory(company_id=company.id)
        character = await character_factory(company_id=company.id, user_player_id=user.id)
        service = CharacterTraitService()

        ritual_traits = await Trait.find(
            Trait.count_based_cost_multiplier == 3,
            Trait.is_archived == False,
        ).to_list(3)
        if len(ritual_traits) < 3:
            pytest.skip("Not enough traits with count_based_cost_multiplier=3 in database")

        # Ensure all traits are in the same parent category
        category_id = ritual_traits[0].parent_category_id
        same_category_traits = [t for t in ritual_traits if t.parent_category_id == category_id]
        if len(same_category_traits) < 3:
            pytest.skip("Not enough rituals in the same category")

        # Add 2 existing rituals with value=1
        for i in range(2):
            await character_trait_factory(
                character_id=character.id, trait=same_category_traits[i], value=1
            )

        # Create the 3rd ritual at value=0 (about to be purchased)
        character_trait = await character_trait_factory(
            character_id=character.id, trait=same_category_traits[2], value=0
        )

        # When calculating upgrade cost
        cost = await service.calculate_upgrade_cost(character_trait, 1)

        # Then cost is 9 (3rd trait: 3 * 3)
        assert cost == 9


class TestCountBasedDowngradeSavings:
    """Test downgrade savings calculation for count-based traits."""

    async def test_removing_only_gift_refunds_2(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        company_factory: Callable[[dict[str, ...]], Company],
        user_factory: Callable[[dict[str, ...]], User],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify removing the only gift refunds 2 (1 x 2)."""
        # Given a character with 1 gift
        company = await company_factory()
        user = await user_factory(company_id=company.id)
        character = await character_factory(
            company_id=company.id, user_player_id=user.id, character_class=CharacterClass.WEREWOLF
        )
        service = CharacterTraitService()

        gift_trait = await Trait.find_one(
            Trait.count_based_cost_multiplier == 2,
            Trait.is_archived == False,
        )
        if gift_trait is None:
            pytest.skip("No trait with count_based_cost_multiplier=2 in database")

        character_trait = await character_trait_factory(
            character_id=character.id, trait=gift_trait, value=1
        )

        # When calculating downgrade savings
        savings = await service.calculate_downgrade_savings(character_trait, 1)

        # Then savings is 2 (1 trait: 1 x 2)
        assert savings == 2

    async def test_removing_fifth_gift_refunds_10(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        company_factory: Callable[[dict[str, ...]], Company],
        user_factory: Callable[[dict[str, ...]], User],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify removing a gift when character has 5 refunds 10 (5 x 2)."""
        # Given a character with 5 gifts
        company = await company_factory()
        user = await user_factory(company_id=company.id)
        character = await character_factory(
            company_id=company.id, user_player_id=user.id, character_class=CharacterClass.WEREWOLF
        )
        service = CharacterTraitService()

        gift_traits = await Trait.find(
            Trait.count_based_cost_multiplier == 2,
            Trait.is_archived == False,
        ).to_list(5)
        if len(gift_traits) < 5:
            pytest.skip("Not enough traits with count_based_cost_multiplier=2 in database")

        for i in range(4):
            await character_trait_factory(character_id=character.id, trait=gift_traits[i], value=1)
        # The 5th gift is the one being removed
        character_trait = await character_trait_factory(
            character_id=character.id, trait=gift_traits[4], value=1
        )

        # When calculating downgrade savings
        savings = await service.calculate_downgrade_savings(character_trait, 1)

        # Then savings is 10 (5th trait: 5 x 2)
        assert savings == 10

    async def test_removing_ritual_refunds_count_times_multiplier(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        company_factory: Callable[[dict[str, ...]], Company],
        user_factory: Callable[[dict[str, ...]], User],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify removing a ritual when character has 3 refunds 9 (3 x 3)."""
        # Given a character with 3 rituals in the same category
        company = await company_factory()
        user = await user_factory(company_id=company.id)
        character = await character_factory(company_id=company.id, user_player_id=user.id)
        service = CharacterTraitService()

        ritual_traits = await Trait.find(
            Trait.count_based_cost_multiplier == 3,
            Trait.is_archived == False,
        ).to_list(3)
        if len(ritual_traits) < 3:
            pytest.skip("Not enough traits with count_based_cost_multiplier=3 in database")

        # Ensure all traits are in the same parent category
        category_id = ritual_traits[0].parent_category_id
        same_category_traits = [t for t in ritual_traits if t.parent_category_id == category_id]
        if len(same_category_traits) < 3:
            pytest.skip("Not enough rituals in the same category")

        for i in range(2):
            await character_trait_factory(
                character_id=character.id, trait=same_category_traits[i], value=1
            )
        # The 3rd ritual is the one being removed
        character_trait = await character_trait_factory(
            character_id=character.id, trait=same_category_traits[2], value=1
        )

        # When calculating downgrade savings
        savings = await service.calculate_downgrade_savings(character_trait, 1)

        # Then savings is 9 (3rd trait: 3 x 3)
        assert savings == 9


class TestCalculateCosts:
    """Test the calculate_upgrade_cost and calculate_downgrade_savings methods."""

    @pytest.mark.parametrize(
        ("current_value", "initial_cost", "upgrade_cost", "decrease_by", "expected"),
        [
            (5, 1, 1, 1, 5),
            (1, 1, 1, 1, 1),
            (1, 1, 2, 1, 1),
        ],
    )
    async def test_calculate_downgrade_savings_initial_cost(
        self,
        initial_cost: int,
        upgrade_cost: int,
        decrease_by: int,
        expected: int,
        current_value: int,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify that the cost to downgrade is correct for the initial cost."""
        service = CharacterTraitService()
        trait = await trait_factory(
            initial_cost=initial_cost,
            upgrade_cost=upgrade_cost,
            max_value=5,
            min_value=0,
            is_custom=True,
        )
        character_trait = await character_trait_factory(
            character_id=PydanticObjectId(),
            trait=trait,
            value=current_value,
        )
        assert await service.calculate_downgrade_savings(character_trait, decrease_by) == expected

    async def test_calculate_downgrade_savings_below_min_value(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify that a validation error is raised if the trait is lowered below the min value."""
        service = CharacterTraitService()
        trait = await trait_factory(min_value=0, is_custom=True)
        character_trait = await character_trait_factory(
            character_id=PydanticObjectId(),
            trait=trait,
            value=1,
        )
        with pytest.raises(ValidationError):
            await service.calculate_downgrade_savings(character_trait, 3)


class TestNonCountBasedCostRegression:
    """Regression test: non-count-based traits still use per-dot cost model after count-based changes."""

    async def test_non_gift_upgrade_cost_unchanged(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify non-gift trait upgrade cost still uses dot-based model."""
        service = CharacterTraitService()
        trait = await trait_factory(
            initial_cost=1, upgrade_cost=2, max_value=5, min_value=0, is_custom=True
        )
        character_trait = await character_trait_factory(
            character_id=PydanticObjectId(), trait=trait, value=2
        )
        cost = await service.calculate_upgrade_cost(character_trait, 2)
        assert cost == 14  # (3x2) + (4x2) = 6 + 8

    async def test_non_gift_downgrade_savings_unchanged(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify non-gift trait downgrade savings still uses dot-based model."""
        service = CharacterTraitService()
        trait = await trait_factory(
            initial_cost=1, upgrade_cost=2, max_value=5, min_value=0, is_custom=True
        )
        character_trait = await character_trait_factory(
            character_id=PydanticObjectId(), trait=trait, value=3
        )
        savings = await service.calculate_downgrade_savings(character_trait, 2)
        assert savings == 10  # (3x2) + (2x2) = 6 + 4


class TestUpdateCharacterWillpower:
    """Test the update_character_willpower method."""

    async def test_update_willpower_skips_non_composure_resolve(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify method returns early for traits that are not Composure or Resolve."""
        # Given a character with a non-Composure/Resolve trait
        character = await character_factory(character_class="MORTAL")

        trait = await Trait.find_one(
            Trait.is_archived == False,
            Trait.name != "Composure",
            Trait.name != "Resolve",
            Trait.name != "Willpower",
            Trait.name != "Courage",
        )
        character_trait = await character_trait_factory(
            character_id=character.id, trait=trait, value=3
        )
        service = CharacterTraitService()

        # When we call update_character_willpower
        # Then no error should be raised (method returns early)
        await service.update_character_willpower(character_trait)

    async def test_update_willpower_creates_willpower_trait(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify willpower trait is created when Composure or Resolve is saved."""
        # Given a character with a Composure trait
        character = await character_factory(character_class="MORTAL")

        composure_trait = await Trait.find_one(Trait.name == "Courage")
        character_trait = await character_trait_factory(
            character_id=character.id, trait=composure_trait, value=3
        )
        service = CharacterTraitService()

        # When we call update_character_willpower
        await service.update_character_willpower(character_trait)

        # Then a willpower trait should be created
        willpower = await CharacterTrait.find_one(
            CharacterTrait.character_id == character.id,
            CharacterTrait.trait.name == "Willpower",  # type: ignore [attr-defined]
            fetch_links=True,
        )
        assert willpower is not None
        assert willpower.value == 3

    async def test_update_willpower_sums_composure_and_resolve(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify willpower equals Composure + Resolve."""
        # Given a character with both Composure and Resolve traits
        character = await character_factory(character_class="MORTAL")

        composure_trait = await Trait.find_one(Trait.name == "Composure")
        resolve_trait = await Trait.find_one(Trait.name == "Resolve")

        await character_trait_factory(character_id=character.id, trait=composure_trait, value=3)
        resolve_ct = await character_trait_factory(
            character_id=character.id, trait=resolve_trait, value=2
        )
        service = CharacterTraitService()

        # When we call update_character_willpower on the resolve trait
        await service.update_character_willpower(resolve_ct)

        # Then willpower should equal Composure + Resolve
        willpower = await CharacterTrait.find_one(
            CharacterTrait.character_id == character.id,
            CharacterTrait.trait.name == "Willpower",  # type: ignore [attr-defined]
            fetch_links=True,
        )
        assert willpower is not None
        assert willpower.value == 5  # 3 + 2


class TestUpdateWerewolfTotalRenown:
    """Test the update_werewolf_total_renown method."""

    async def test_update_renown_skips_non_renown_traits(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify method returns early for traits that are not Honor, Wisdom, or Glory."""
        # Given a werewolf character with a non-renown trait
        character = await character_factory(character_class="WEREWOLF")

        trait = await Trait.find_one(
            Trait.is_archived == False,
            Trait.name != "Honor",
            Trait.name != "Wisdom",
            Trait.name != "Glory",
        )
        character_trait = await character_trait_factory(
            character_id=character.id, trait=trait, value=3
        )
        service = CharacterTraitService()

        # Store initial renown value
        initial_renown = character.werewolf_attributes.total_renown

        # When we call update_werewolf_total_renown
        await service.update_werewolf_total_renown(character_trait)

        # Then the total renown should not change
        await character.sync()
        assert character.werewolf_attributes.total_renown == initial_renown

    async def test_update_renown_skips_non_werewolf(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify method returns early for non-werewolf characters."""
        # Given a mortal character with a renown trait (shouldn't happen but testing edge case)
        character = await character_factory(character_class="MORTAL")

        honor_trait = await Trait.find_one(Trait.name == "Honor")
        if honor_trait:
            character_trait = await character_trait_factory(
                character_id=character.id, trait=honor_trait, value=2
            )
            service = CharacterTraitService()

            # When we call update_werewolf_total_renown
            # Then no error should be raised (method returns early)
            await service.update_werewolf_total_renown(character_trait)

    async def test_update_renown_sums_honor_wisdom_glory(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify total_renown equals Honor + Wisdom + Glory."""
        # Given a werewolf character with renown traits
        character = await character_factory(character_class="WEREWOLF")

        honor_trait = await Trait.find_one(Trait.name == "Honor")
        wisdom_trait = await Trait.find_one(Trait.name == "Wisdom")
        glory_trait = await Trait.find_one(Trait.name == "Glory")

        # Skip if renown traits don't exist
        if not all([honor_trait, wisdom_trait, glory_trait]):
            pytest.skip("Renown traits not found in database")

        await character_trait_factory(character_id=character.id, trait=honor_trait, value=2)
        await character_trait_factory(character_id=character.id, trait=wisdom_trait, value=3)
        glory_ct = await character_trait_factory(
            character_id=character.id, trait=glory_trait, value=1
        )
        service = CharacterTraitService()

        # When we call update_werewolf_total_renown on the glory trait
        await service.update_werewolf_total_renown(glory_ct)

        # Then total_renown should equal Honor + Wisdom + Glory
        await character.sync()
        assert character.werewolf_attributes.total_renown == 6  # 2 + 3 + 1

        # Cleanup
        await character.delete()


class TestAfterSave:
    """Test the after_save orchestration method."""

    async def test_after_save_calls_willpower_and_renown(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        mocker: Any,
    ) -> None:
        """Verify after_save calls both update methods."""
        # Given a character with a trait
        character = await character_factory(character_class="MORTAL")

        trait = await Trait.find_one(Trait.is_archived == False)
        character_trait = await character_trait_factory(
            character_id=character.id, trait=trait, value=1
        )
        service = CharacterTraitService()

        # When we spy on the service methods
        spy_willpower = mocker.spy(service, "update_character_willpower")
        spy_renown = mocker.spy(service, "update_werewolf_total_renown")

        # And call after_save
        await service.after_save(character_trait)

        # Then both update methods should be called
        spy_willpower.assert_called_once_with(character_trait)
        spy_renown.assert_called_once_with(character_trait)


class TestAddConstantTraitToCharacter:
    """Test the add_constant_trait_to_character method."""

    async def test_add_constant_trait_to_character_no_cost(
        self,
        get_company_user_character: tuple[Company, User, Character],
        mocker: Any,
    ) -> None:
        """Verify the trait is added to the character."""
        # Given a character and trait
        company, user, character = get_company_user_character
        trait = await Trait.find_one(Trait.is_archived == False)
        spy_get_trait_by_id = mocker.spy(GetModelByIdValidationService, "get_trait_by_id")
        spy_after_save = mocker.spy(CharacterTraitService, "after_save")
        spyguard_user_can_manage_character = mocker.spy(
            CharacterTraitService, "guard_user_can_manage_character"
        )
        spy_guard_permissions_free_trait_changes = mocker.spy(
            CharacterTraitService, "_guard_permissions_free_trait_changes"
        )
        service = CharacterTraitService()

        # When we call add_constant_trait_to_character
        result = await service.add_constant_trait_to_character(
            company=company,
            user=user,
            character=character,
            trait_id=trait.id,
            value=2,
            currency=TraitModifyCurrency.NO_COST,
        )

        # Then the trait should be added to the character
        await character.sync()
        assert result.id in character.character_trait_ids
        spy_get_trait_by_id.assert_called_once_with(ANY, trait.id)
        spy_after_save.assert_called_once_with(ANY, result)
        spyguard_user_can_manage_character.assert_called_once()
        spy_guard_permissions_free_trait_changes.assert_called_once()
        assert result.value == 2
        assert result.trait.id == trait.id
        assert result.character_id == character.id

    async def test_add_constant_trait_to_character_conflict(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify a conflict error is raised if the trait already exists on the character."""
        # Given a character with an existing trait
        company, user, character = get_company_user_character
        trait = await Trait.find_one(Trait.is_archived == False)
        await character_trait_factory(character_id=character.id, trait=trait, value=1)

        # When we try to add the same trait again
        # Then a ConflictError should be raised
        service = CharacterTraitService()
        with pytest.raises(ConflictError):
            await service.add_constant_trait_to_character(
                company=company,
                user=user,
                character=character,
                trait_id=trait.id,
                value=2,
                currency=TraitModifyCurrency.NO_COST,
            )

    async def test_add_constant_trait_to_character_with_xp(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        company_factory: Callable[[dict[str, ...]], Company],
        mocker: Any,
    ) -> None:
        """Verify the trait is added using XP currency."""
        # Given a character with XP
        company = await company_factory()
        campaign = await campaign_factory()
        user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        await user.add_xp(campaign.id, 100)
        character = await character_factory(
            user_player_id=user.id, campaign_id=campaign.id, company_id=company.id
        )
        trait = await Trait.find_one(Trait.is_archived == False)
        spy_purchase = mocker.spy(CharacterTraitService, "_apply_xp_change")

        # When we add a trait with XP currency
        service = CharacterTraitService()
        result = await service.add_constant_trait_to_character(
            company=company,
            user=user,
            character=character,
            trait_id=trait.id,
            value=2,
            currency=TraitModifyCurrency.XP,
        )

        # Then the trait should be added and XP spent
        assert result.value == 2
        assert result.trait.id == trait.id
        assert result.character_id == character.id
        spy_purchase.assert_called_once()

        # Cleanup
        await character.delete()

    async def test_add_constant_trait_to_character_with_starting_points(
        self,
        get_company_user_character: tuple[Company, User, Character],
        mocker: Any,
    ) -> None:
        """Verify the trait is added using starting points currency."""
        # Given a character with starting points
        company, user, character = get_company_user_character
        character.starting_points = 100
        await character.save()
        trait = await Trait.find_one(Trait.is_archived == False)
        spy_purchase_sp = mocker.spy(CharacterTraitService, "_apply_starting_points_change")

        # When we add a trait with STARTING_POINTS currency
        service = CharacterTraitService()
        result = await service.add_constant_trait_to_character(
            company=company,
            user=user,
            character=character,
            trait_id=trait.id,
            value=2,
            currency=TraitModifyCurrency.STARTING_POINTS,
        )

        # Then the trait should be added and starting points spent
        assert result.value == 2
        assert result.trait.id == trait.id
        assert result.character_id == character.id
        spy_purchase_sp.assert_called_once()

    async def test_add_constant_trait_to_character_over_max_value(
        self,
        get_company_user_character: tuple[Company, User, Character],
    ) -> None:
        """Verify a validation error is raised if the trait is added above the max value."""
        # Given a character and trait
        company, user, character = get_company_user_character
        trait = await Trait.find_one(Trait.is_archived == False)

        # When we call add_constant_trait_to_character
        # Then a validation error should be raised
        service = CharacterTraitService()
        with pytest.raises(ValidationError):
            await service.add_constant_trait_to_character(
                company=company,
                user=user,
                character=character,
                trait_id=trait.id,
                value=trait.max_value + 1,
                currency=TraitModifyCurrency.NO_COST,
            )

    async def test_add_constant_trait_to_character_below_min_value(
        self,
        get_company_user_character: tuple[Company, User, Character],
    ) -> None:
        """Verify a validation error is raised if the trait is added below the min value."""
        # Given a character and trait
        company, user, character = get_company_user_character
        trait = await Trait.find_one(Trait.is_archived == False)
        service = CharacterTraitService()
        with pytest.raises(ValidationError):
            await service.add_constant_trait_to_character(
                company=company,
                user=user,
                character=character,
                trait_id=trait.id,
                value=trait.min_value - 1,
                currency=TraitModifyCurrency.NO_COST,
            )


class TestGuardHasMinimumRenown:
    """Test the renown guard when adding gifts."""

    async def test_add_gift_insufficient_renown(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        company_factory: Callable[[dict[str, ...]], Company],
    ) -> None:
        """Verify adding a gift fails when character renown is below minimum."""
        # Given a werewolf character with total_renown=0
        company = await company_factory()
        campaign = await campaign_factory()
        user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        character = await character_factory(
            user_player_id=user.id,
            campaign_id=campaign.id,
            company_id=company.id,
            character_class=CharacterClass.WEREWOLF,
        )
        assert character.werewolf_attributes.total_renown == 0

        # Given a gift trait with minimum_renown > 0
        gift_trait = await Trait.find_one(
            Trait.gift_attributes != None,
            Trait.gift_attributes.minimum_renown != None,
            Trait.gift_attributes.minimum_renown > 0,
            Trait.is_archived == False,
        )
        if gift_trait is None:
            pytest.skip("No gift with minimum_renown found in database")

        # When adding the gift with XP currency
        # Then a ValidationError is raised
        service = CharacterTraitService()
        with pytest.raises(ValidationError, match="Renown"):
            await service.add_constant_trait_to_character(
                company=company,
                user=user,
                character=character,
                trait_id=gift_trait.id,
                value=1,
                currency=TraitModifyCurrency.XP,
            )

    async def test_add_gift_sufficient_renown(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        company_factory: Callable[[dict[str, ...]], Company],
    ) -> None:
        """Verify adding a gift succeeds when character renown meets minimum."""
        # Given a werewolf character with enough renown and XP
        company = await company_factory()
        campaign = await campaign_factory()
        user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        await user.add_xp(campaign.id, 500)
        character = await character_factory(
            user_player_id=user.id,
            campaign_id=campaign.id,
            company_id=company.id,
            character_class=CharacterClass.WEREWOLF,
        )

        # Given a gift trait with minimum_renown > 0
        gift_trait = await Trait.find_one(
            Trait.gift_attributes != None,
            Trait.gift_attributes.minimum_renown != None,
            Trait.gift_attributes.minimum_renown > 0,
            Trait.is_archived == False,
        )
        if gift_trait is None:
            pytest.skip("No gift with minimum_renown found in database")

        # Set character's total_renown above the requirement
        character.werewolf_attributes.total_renown = gift_trait.gift_attributes.minimum_renown + 1
        await character.save()

        # When adding the gift with XP
        service = CharacterTraitService()
        result = await service.add_constant_trait_to_character(
            company=company,
            user=user,
            character=character,
            trait_id=gift_trait.id,
            value=1,
            currency=TraitModifyCurrency.XP,
        )

        # Then the trait is added successfully
        assert result.value == 1

    async def test_add_gift_no_cost_bypasses_renown_check(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        company_factory: Callable[[dict[str, ...]], Company],
    ) -> None:
        """Verify adding a gift with NO_COST bypasses the renown check."""
        # Given a werewolf character with total_renown=0
        company = await company_factory()
        campaign = await campaign_factory()
        user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        character = await character_factory(
            user_player_id=user.id,
            campaign_id=campaign.id,
            company_id=company.id,
            character_class=CharacterClass.WEREWOLF,
        )
        assert character.werewolf_attributes.total_renown == 0

        # Given a gift trait with minimum_renown > 0
        gift_trait = await Trait.find_one(
            Trait.gift_attributes != None,
            Trait.gift_attributes.minimum_renown != None,
            Trait.gift_attributes.minimum_renown > 0,
            Trait.is_archived == False,
        )
        if gift_trait is None:
            pytest.skip("No gift with minimum_renown found in database")

        # When adding the gift with NO_COST
        service = CharacterTraitService()
        result = await service.add_constant_trait_to_character(
            company=company,
            user=user,
            character=character,
            trait_id=gift_trait.id,
            value=1,
            currency=TraitModifyCurrency.NO_COST,
        )

        # Then the trait is added successfully despite insufficient renown
        assert result.value == 1

    async def test_add_gift_no_minimum_renown_succeeds(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        company_factory: Callable[[dict[str, ...]], Company],
    ) -> None:
        """Verify adding a gift with minimum_renown=None skips the check."""
        # Given a werewolf character with XP
        company = await company_factory()
        campaign = await campaign_factory()
        user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        await user.add_xp(campaign.id, 500)
        character = await character_factory(
            user_player_id=user.id,
            campaign_id=campaign.id,
            company_id=company.id,
            character_class=CharacterClass.WEREWOLF,
        )

        # Given a gift trait with no minimum_renown requirement
        gift_trait = await Trait.find_one(
            Trait.gift_attributes != None,
            Trait.gift_attributes.minimum_renown == None,
            Trait.is_archived == False,
        )
        if gift_trait is None:
            pytest.skip("No gift without minimum_renown found in database")

        # When adding the gift with XP currency so the guard is actually invoked
        service = CharacterTraitService()
        result = await service.add_constant_trait_to_character(
            company=company,
            user=user,
            character=character,
            trait_id=gift_trait.id,
            value=1,
            currency=TraitModifyCurrency.XP,
        )

        # Then the trait is added successfully
        assert result.value == 1

    async def test_add_non_gift_trait_skips_renown_check(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        company_factory: Callable[[dict[str, ...]], Company],
    ) -> None:
        """Verify adding a non-gift trait does not trigger the renown guard."""
        # Given a werewolf character with XP
        company = await company_factory()
        campaign = await campaign_factory()
        user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        await user.add_xp(campaign.id, 500)
        character = await character_factory(
            user_player_id=user.id,
            campaign_id=campaign.id,
            company_id=company.id,
            character_class=CharacterClass.WEREWOLF,
        )

        # Given a non-gift trait
        non_gift_trait = await Trait.find_one(
            Trait.gift_attributes == None,
            Trait.is_archived == False,
        )
        if non_gift_trait is None:
            pytest.skip("No non-gift trait found in database")

        # When adding the trait with XP currency so the guard is actually invoked
        service = CharacterTraitService()
        result = await service.add_constant_trait_to_character(
            company=company,
            user=user,
            character=character,
            trait_id=non_gift_trait.id,
            value=1,
            currency=TraitModifyCurrency.XP,
        )

        # Then the trait is added successfully
        assert result.value == 1


class TestCreateCustomTrait:
    """Test the create_custom_trait method."""

    async def test_create_custom_trait(
        self,
        get_company_user_character: tuple[Company, User, Character],
        mocker: Any,
    ) -> None:
        """Verify the trait is created and added to the character."""
        # Given a character and trait
        company, user, character = get_company_user_character
        trait_category = await TraitCategory.find_one(TraitCategory.is_archived == False)
        dto = CharacterTraitCreateCustomDTO(
            name="Test Trait",
            description="Test Description",
            max_value=5,
            min_value=0,
            show_when_zero=True,
            parent_category_id=trait_category.id,
            value=1,
        )
        spy_after_save = mocker.spy(CharacterTraitService, "after_save")
        spy_get_trait_category_by_id = mocker.spy(
            GetModelByIdValidationService, "get_trait_category_by_id"
        )
        spyguard_user_can_manage_character = mocker.spy(
            CharacterTraitService, "guard_user_can_manage_character"
        )
        spy_guard_permissions_free_trait_changes = mocker.spy(
            CharacterTraitService, "_guard_permissions_free_trait_changes"
        )

        # When we create the trait
        service = CharacterTraitService()
        result = await service.create_custom_trait(
            company=company,
            user=user,
            character=character,
            data=dto,
        )

        # Then the trait should be created and added to the character
        await character.sync()
        assert result.id in character.character_trait_ids
        assert result.value == 1
        assert result.trait.name == "Test Trait"
        assert result.trait.description == "Test Description"
        assert result.trait.max_value == 5
        assert result.trait.min_value == 0
        assert result.trait.show_when_zero == True
        assert result.trait.parent_category_id == trait_category.id
        assert result.trait.initial_cost == trait_category.initial_cost
        assert result.trait.upgrade_cost == trait_category.upgrade_cost
        assert result.trait.is_custom == True
        assert result.trait.custom_for_character_id == character.id
        assert result.character_id == character.id
        spy_after_save.assert_called_once_with(ANY, result)
        spy_get_trait_category_by_id.assert_called_once_with(ANY, trait_category.id)
        spyguard_user_can_manage_character.assert_called_once()
        spy_guard_permissions_free_trait_changes.assert_called_once()

    async def test_create_custom_trait_conflict_with_character_trait(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify a conflict error is raised if the trait already exists on the character."""
        # Given a character and trait
        company, user, character = get_company_user_character
        trait = await Trait.find_one(Trait.is_archived == False)
        await character_trait_factory(character_id=character.id, trait=trait)
        trait_category = await TraitCategory.find_one(TraitCategory.is_archived == False)
        dto = CharacterTraitCreateCustomDTO(
            name=trait.name,
            description="Test Description",
            max_value=5,
            min_value=0,
            show_when_zero=True,
            parent_category_id=trait_category.id,
            value=1,
        )

        # When we create the trait
        # Then a conflict error should be raised if the trait is created again
        service = CharacterTraitService()
        with pytest.raises(ConflictError):
            await service.create_custom_trait(
                company=company,
                user=user,
                character=character,
                data=dto,
            )

    async def test_create_custom_trait_conflict_with_non_assigned_trait_name(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify a conflict error is raised if the trait name exists on any trait in the database."""
        # Given a character and trait
        company, user, character = get_company_user_character

        all_traits = await Trait.find(
            Trait.is_archived == False, Trait.is_custom == False
        ).to_list()
        all_character_traits = await CharacterTrait.find(
            CharacterTrait.character_id == character.id,
            fetch_links=True,
        ).to_list()

        unassigned_trait = next(
            (
                trait
                for trait in all_traits
                if trait.name not in [trait.trait.name for trait in all_character_traits]
            ),
            None,
        )
        if not unassigned_trait:
            msg = "No unassigned trait found"
            raise pytest.fail(msg)

        dto = CharacterTraitCreateCustomDTO(
            name=unassigned_trait.name,
            description="Test Description",
            max_value=5,
            min_value=0,
            show_when_zero=True,
            parent_category_id=unassigned_trait.parent_category_id,
            value=1,
        )

        # When we create the trait
        # Then a conflict error should be raised if the trait is created again
        service = CharacterTraitService()
        with pytest.raises(ConflictError):
            await service.create_custom_trait(
                company=company,
                user=user,
                character=character,
                data=dto,
            )


class TestChangeCharacterTraitValue:
    """Test the change_character_trait_value method."""

    async def test_increase_character_trait_value(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        mocker: Any,
    ) -> None:
        """Verify the trait value is increased."""
        # Given a character and trait
        company, user, character = get_company_user_character
        character_trait = await character_trait_factory(value=0, character_id=character.id)
        spy_after_save = mocker.spy(CharacterTraitService, "after_save")
        spy_guard_is_safe_increase = mocker.spy(CharacterTraitService, "_guard_is_safe_increase")
        spyguard_user_can_manage_character = mocker.spy(
            CharacterTraitService, "guard_user_can_manage_character"
        )
        spy_guard_permissions_free_trait_changes = mocker.spy(
            CharacterTraitService, "_guard_permissions_free_trait_changes"
        )

        # When we increase the trait value
        service = CharacterTraitService()
        result = await service.increase_character_trait_value(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=1,
        )

        # Then the trait value should be increased
        await character_trait.sync()
        assert result.value == 1
        spy_after_save.assert_called_once_with(ANY, result)
        spyguard_user_can_manage_character.assert_called_once()
        spy_guard_permissions_free_trait_changes.assert_called_once()
        spy_guard_is_safe_increase.assert_called_once_with(ANY, character_trait, 1)

    async def test_decrease_character_trait_value(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        mocker: Any,
    ) -> None:
        """Verify the trait value is decreased."""
        # Given a character and trait
        company, user, character = get_company_user_character
        character_trait = await character_trait_factory(value=5, character_id=character.id)
        spy_after_save = mocker.spy(CharacterTraitService, "after_save")
        spy_guard_is_safe_decrease = mocker.spy(CharacterTraitService, "_guard_is_safe_decrease")
        spyguard_user_can_manage_character = mocker.spy(
            CharacterTraitService, "guard_user_can_manage_character"
        )
        spy_guard_permissions_free_trait_changes = mocker.spy(
            CharacterTraitService, "_guard_permissions_free_trait_changes"
        )

        # When we decrease the trait value
        service = CharacterTraitService()
        result = await service.decrease_character_trait_value(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=1,
        )

        # Then the trait value should be decreased
        await character_trait.sync()
        assert result.value == 4
        spy_after_save.assert_called_once_with(ANY, result)
        spyguard_user_can_manage_character.assert_called_once()
        spy_guard_permissions_free_trait_changes.assert_called_once()
        spy_guard_is_safe_decrease.assert_called_once_with(ANY, character_trait, 1)

    async def test_purchase_trait_value_with_xp(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        mocker: Any,
    ) -> None:
        """Verify the trait value is purchased with xp."""
        # Given a character and trait
        campaign = await campaign_factory()
        target_user = await user_factory()
        await target_user.add_xp(campaign.id, 100)

        spy_get_user_by_id = mocker.spy(GetModelByIdValidationService, "get_user_by_id")
        spyguard_user_can_manage_character = mocker.spy(
            CharacterTraitService, "guard_user_can_manage_character"
        )
        spy_guard_is_safe_increase = mocker.spy(CharacterTraitService, "_guard_is_safe_increase")
        spy_calculate_upgrade_cost = mocker.spy(CharacterTraitService, "_calculate_upgrade_cost")

        character = await character_factory(user_player_id=target_user.id, campaign_id=campaign.id)
        character_trait = await character_trait_factory(value=1, character_id=character.id)

        # When we purchase the trait value with xp
        service = CharacterTraitService()
        result = await service._apply_xp_change(
            user=target_user,
            character=character,
            character_trait=character_trait,
            num_dots=1,
            is_increase=True,
        )

        # Then the trait value should be purchased
        await character_trait.sync()
        assert result.value == 2

        spy_get_user_by_id.assert_called_once_with(ANY, target_user.id)
        spyguard_user_can_manage_character.assert_called_once()
        spy_guard_is_safe_increase.assert_called_once_with(ANY, character_trait, 1)
        spy_calculate_upgrade_cost.assert_called_once_with(
            ANY,
            character_trait,
            1,
            character_id=character_trait.character_id,
        )
        await target_user.sync()
        campaign_experience = await target_user.get_or_create_campaign_experience(campaign.id)
        assert (
            campaign_experience.xp_current
            == 100 - character_trait.trait.initial_cost - character_trait.trait.upgrade_cost
        )
        assert campaign_experience.xp_total == 100

        # Cleanup
        await character.delete()
        await character_trait.delete()

    async def test_purchase_flaw_trait_with_xp_grants_xp(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify increasing a flaw trait grants XP instead of spending it."""
        # Given a character with a flaw trait and some XP
        campaign = await campaign_factory()
        target_user = await user_factory()
        await target_user.add_xp(campaign.id, 100)

        character = await character_factory(user_player_id=target_user.id, campaign_id=campaign.id)
        flaws_category = await TraitCategory.find_one(TraitCategory.name == "Flaws")
        flaw_trait = await trait_factory(
            parent_category_id=flaws_category.id,
            initial_cost=1,
            upgrade_cost=2,
            max_value=5,
            min_value=0,
        )
        character_trait = await character_trait_factory(
            character_id=character.id, trait=flaw_trait, value=1
        )

        # When we purchase an increase for the flaw trait with XP
        service = CharacterTraitService()
        result = await service._apply_xp_change(
            user=target_user,
            character=character,
            character_trait=character_trait,
            num_dots=1,
            is_increase=True,
        )

        # Then the trait value should increase and XP should be GRANTED (not spent)
        assert result.value == 2
        await target_user.sync()
        campaign_experience = await target_user.get_or_create_campaign_experience(campaign.id)
        cost = 2 * 2  # value 2 * upgrade_cost 2 = 4
        assert campaign_experience.xp_current == 100 + cost

        # Cleanup
        await character.delete()
        await character_trait.delete()

    async def test_purchase_trait_value_with_xp_not_enough_xp(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
    ) -> None:
        """Verify the trait value is purchased with xp."""
        # Given a character and trait
        campaign = await campaign_factory()
        target_user = await user_factory()
        character = await character_factory(user_player_id=target_user.id, campaign_id=campaign.id)
        character_trait = await character_trait_factory(value=1, character_id=character.id)

        # When we purchase the trait value with xp
        service = CharacterTraitService()
        with pytest.raises(NotEnoughXPError):
            await service._apply_xp_change(
                character=character,
                user=target_user,
                character_trait=character_trait,
                num_dots=1,
                is_increase=True,
            )

    async def test_refund_trait_value_with_xp(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        mocker: Any,
    ) -> None:
        """Verify the trait value is refunded with xp."""
        spy_get_user_by_id = mocker.spy(GetModelByIdValidationService, "get_user_by_id")
        spyguard_user_can_manage_character = mocker.spy(
            CharacterTraitService, "guard_user_can_manage_character"
        )
        spy_guard_is_safe_decrease = mocker.spy(CharacterTraitService, "_guard_is_safe_decrease")
        spy_calculate_downgrade_savings = mocker.spy(
            CharacterTraitService, "_calculate_downgrade_savings"
        )
        # Given a character and trait
        campaign = await campaign_factory()
        target_user = await user_factory()
        await target_user.add_xp(campaign.id, 100)

        character = await character_factory(user_player_id=target_user.id, campaign_id=campaign.id)
        character_trait = await character_trait_factory(value=5, character_id=character.id)

        # When we refund the trait value with xp
        service = CharacterTraitService()
        result = await service._apply_xp_change(
            character=character,
            user=target_user,
            character_trait=character_trait,
            num_dots=1,
            is_increase=False,
        )

        # Then the trait value should be refunded
        await character_trait.sync()
        assert result.value == 4
        await target_user.sync()
        campaign_experience = await target_user.get_or_create_campaign_experience(campaign.id)
        assert campaign_experience.xp_current == 100 + character_trait.trait.initial_cost * 5

        spy_get_user_by_id.assert_called_once_with(ANY, target_user.id)
        spyguard_user_can_manage_character.assert_called_once()
        spy_guard_is_safe_decrease.assert_called_once_with(ANY, character_trait, 1)
        spy_calculate_downgrade_savings.assert_called_once_with(
            ANY,
            character_trait,
            1,
            character_id=character_trait.character_id,
        )

        # Cleanup
        await character.delete()
        await character_trait.delete()

    async def test_purchase_trait_increase_with_starting_points(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        mocker: Any,
    ) -> None:
        """Verify the trait value is increased with starting points."""
        # Given a character and trait
        _, user, character = get_company_user_character
        character.starting_points = 100
        await character.save()

        trait = await Trait.find_one(Trait.is_archived == False)
        character_trait = await character_trait_factory(
            value=trait.min_value,
            trait=trait,
            character_id=character.id,
        )

        spyguard_user_can_manage_character = mocker.spy(
            CharacterTraitService, "guard_user_can_manage_character"
        )
        spy_guard_is_safe_increase = mocker.spy(CharacterTraitService, "_guard_is_safe_increase")
        spy_calculate_upgrade_cost = mocker.spy(CharacterTraitService, "_calculate_upgrade_cost")
        spy_after_save = mocker.spy(CharacterTraitService, "after_save")

        # When we purchase the trait value with starting points
        service = CharacterTraitService()
        result = await service._apply_starting_points_change(
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=1,
            is_increase=True,
        )

        # Then the trait value should be purchased
        await character_trait.sync()
        assert result.value == trait.min_value + 1

        spyguard_user_can_manage_character.assert_called_once()
        spy_guard_is_safe_increase.assert_called_once_with(ANY, character_trait, 1)
        spy_calculate_upgrade_cost.assert_called_once_with(
            ANY,
            character_trait,
            1,
            character_id=character_trait.character_id,
        )
        spy_after_save.assert_called_once_with(ANY, result)
        spy_guard_is_safe_increase.assert_called_once_with(ANY, character_trait, 1)
        await character.sync()
        assert character.starting_points == 100 - (character_trait.trait.initial_cost * 2)

        # Cleanup
        await character_trait.delete()

    async def test_purchase_not_enough_starting_points(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        mocker: Any,
    ) -> None:
        """Verify the trait value is purchased with starting points."""
        # Given a character and trait
        _, user, character = get_company_user_character
        character.starting_points = 1
        await character.save()
        character_trait = await character_trait_factory(value=1, character_id=character.id)

        # When we purchase the trait value with starting points
        service = CharacterTraitService()
        with pytest.raises(ValidationError, match="Not enough starting points"):
            await service._apply_starting_points_change(
                user=user,
                character=character,
                character_trait=character_trait,
                num_dots=1,
                is_increase=True,
            )

        # Cleanup
        await character_trait.delete()

    async def test_purchase_flaw_trait_with_starting_points_grants_sp(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify increasing a flaw trait grants starting points instead of spending them."""
        # Given a character with a flaw trait and starting points
        _, user, character = get_company_user_character
        character.starting_points = 100
        await character.save()

        flaws_category = await TraitCategory.find_one(TraitCategory.name == "Flaws")
        flaw_trait = await trait_factory(
            parent_category_id=flaws_category.id,
            initial_cost=1,
            upgrade_cost=2,
            max_value=5,
            min_value=0,
        )
        character_trait = await character_trait_factory(
            character_id=character.id, trait=flaw_trait, value=1
        )

        # When we purchase an increase for the flaw trait with starting points
        service = CharacterTraitService()
        result = await service._apply_starting_points_change(
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=1,
            is_increase=True,
        )

        # Then the trait value should increase and starting points should be GRANTED
        assert result.value == 2
        await character.sync()
        cost = 2 * 2  # value 2 * upgrade_cost 2 = 4
        assert character.starting_points == 100 + cost

        # Cleanup
        await character_trait.delete()

    async def refund_trait_decrease_with_starting_points(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        mocker: Any,
    ) -> None:
        """Verify the trait value is refunded with starting points."""
        # Given a character and trait
        _, user, character = get_company_user_character
        character.starting_points = 100
        await character.save()

        character_trait = await character_trait_factory(value=5, character_id=character.id)
        spy_guard_is_safe_decrease = mocker.spy(CharacterTraitService, "_guard_is_safe_decrease")
        spy_after_save = mocker.spy(CharacterTraitService, "after_save")
        spyguard_user_can_manage_character = mocker.spy(
            CharacterTraitService, "guard_user_can_manage_character"
        )
        spy_guard_is_safe_decrease = mocker.spy(CharacterTraitService, "_guard_is_safe_decrease")
        spy_calculate_downgrade_savings = mocker.spy(
            CharacterTraitService, "_calculate_downgrade_savings"
        )

        # When we refund the trait value with starting points
        service = CharacterTraitService()
        result = await service._apply_starting_points_change(
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=1,
            is_increase=False,
        )

        # Then the trait value should be refunded
        await character_trait.sync()
        assert result.value == 0
        await character.sync()
        assert character.starting_points == 100 + character_trait.trait.initial_cost * 5
        spy_after_save.assert_called_once_with(ANY, result)
        spy_guard_is_safe_decrease.assert_called_once_with(ANY, character_trait, 1)
        spy_calculate_downgrade_savings.assert_called_once_with(
            ANY,
            character_trait,
            1,
            character_id=character_trait.character_id,
        )
        spyguard_user_can_manage_character.assert_called_once()

        # Cleanup
        await character_trait.delete()

    async def test_refund_flaw_trait_with_xp_spends_xp(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify decreasing a flaw trait spends XP instead of granting it."""
        # Given a character with a flaw trait and enough XP to cover the cost
        campaign = await campaign_factory()
        target_user = await user_factory()
        await target_user.add_xp(campaign.id, 100)

        character = await character_factory(user_player_id=target_user.id, campaign_id=campaign.id)
        flaws_category = await TraitCategory.find_one(TraitCategory.name == "Flaws")
        flaw_trait = await trait_factory(
            parent_category_id=flaws_category.id,
            initial_cost=1,
            upgrade_cost=2,
            max_value=5,
            min_value=0,
        )
        character_trait = await character_trait_factory(
            character_id=character.id, trait=flaw_trait, value=3
        )

        # When we refund (decrease) the flaw trait with XP
        service = CharacterTraitService()
        result = await service._apply_xp_change(
            character=character,
            user=target_user,
            character_trait=character_trait,
            num_dots=1,
            is_increase=False,
        )

        # Then the trait value should decrease and XP should be SPENT (not granted)
        assert result.value == 2
        await target_user.sync()
        campaign_experience = await target_user.get_or_create_campaign_experience(campaign.id)
        savings = 3 * 2  # value 3 * upgrade_cost 2 = 6
        assert campaign_experience.xp_current == 100 - savings

        # Cleanup
        await character.delete()
        await character_trait.delete()

    async def test_refund_flaw_trait_with_xp_not_enough_xp(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify decreasing a flaw trait raises error when not enough XP."""
        # Given a character with a flaw trait and NO XP
        campaign = await campaign_factory()
        target_user = await user_factory()

        character = await character_factory(user_player_id=target_user.id, campaign_id=campaign.id)
        flaws_category = await TraitCategory.find_one(TraitCategory.name == "Flaws")
        flaw_trait = await trait_factory(
            parent_category_id=flaws_category.id,
            initial_cost=1,
            upgrade_cost=2,
            max_value=5,
            min_value=0,
        )
        character_trait = await character_trait_factory(
            character_id=character.id, trait=flaw_trait, value=3
        )

        # When we try to refund the flaw trait with XP
        # Then a NotEnoughXPError should be raised
        service = CharacterTraitService()
        with pytest.raises(NotEnoughXPError):
            await service._apply_xp_change(
                character=character,
                user=target_user,
                character_trait=character_trait,
                num_dots=1,
                is_increase=False,
            )

        # Cleanup
        await character.delete()
        await character_trait.delete()

    async def test_refund_flaw_trait_with_starting_points_spends_sp(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify decreasing a flaw trait spends starting points instead of granting them."""
        # Given a character with a flaw trait and starting points
        _, user, character = get_company_user_character
        character.starting_points = 100
        await character.save()

        flaws_category = await TraitCategory.find_one(TraitCategory.name == "Flaws")
        flaw_trait = await trait_factory(
            parent_category_id=flaws_category.id,
            initial_cost=1,
            upgrade_cost=2,
            max_value=5,
            min_value=0,
        )
        character_trait = await character_trait_factory(
            character_id=character.id, trait=flaw_trait, value=3
        )

        # When we refund (decrease) the flaw trait with starting points
        service = CharacterTraitService()
        result = await service._apply_starting_points_change(
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=1,
            is_increase=False,
        )

        # Then the trait value should decrease and starting points should be SPENT
        assert result.value == 2
        await character.sync()
        savings = 3 * 2  # value 3 * upgrade_cost 2 = 6
        assert character.starting_points == 100 - savings

        # Cleanup
        await character_trait.delete()

    async def test_refund_flaw_trait_with_starting_points_not_enough_sp(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify decreasing a flaw trait raises error when not enough starting points."""
        # Given a character with a flaw trait and insufficient starting points
        _, user, character = get_company_user_character
        character.starting_points = 0
        await character.save()

        flaws_category = await TraitCategory.find_one(TraitCategory.name == "Flaws")
        flaw_trait = await trait_factory(
            parent_category_id=flaws_category.id,
            initial_cost=1,
            upgrade_cost=2,
            max_value=5,
            min_value=0,
        )
        character_trait = await character_trait_factory(
            character_id=character.id, trait=flaw_trait, value=3
        )

        # When we try to refund the flaw trait with starting points
        # Then a ValidationError should be raised
        service = CharacterTraitService()
        with pytest.raises(ValidationError, match="Not enough starting points"):
            await service._apply_starting_points_change(
                user=user,
                character=character,
                character_trait=character_trait,
                num_dots=1,
                is_increase=False,
            )

        # Cleanup
        await character_trait.delete()


class TestGetValueOptions:
    """Test the get_value_options method."""

    async def test_get_value_options_returns_correct_structure(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify get_value_options returns correct response structure."""
        # Given a character with XP and starting points
        campaign = await campaign_factory()
        target_user = await user_factory()
        await target_user.add_xp(campaign.id, 50)

        character = await character_factory(
            user_player_id=target_user.id,
            campaign_id=campaign.id,
            starting_points=10,
        )

        trait = await trait_factory(
            initial_cost=1, upgrade_cost=2, max_value=5, min_value=0, is_custom=True
        )
        character_trait = await character_trait_factory(
            character_id=character.id, trait=trait, value=2
        )

        # When we get value options
        service = CharacterTraitService()
        result = await service.get_value_options(
            character=character,
            character_trait=character_trait,
        )

        # Then the response should have the correct structure
        assert result.current_value == 2
        assert result.trait.min_value == 0
        assert result.trait.max_value == 5
        assert result.xp_current == 50
        assert result.starting_points_current == 10
        assert result.trait == character_trait.trait

        # Should have options for values 0, 1, 3, 4, 5 (not 2, which is current)
        assert "2" not in result.options
        assert "0" in result.options
        assert "1" in result.options
        assert "3" in result.options
        assert "4" in result.options
        assert "5" in result.options

        # Decrease options should have direction "decrease"
        assert result.options["0"].direction == "decrease"
        assert result.options["1"].direction == "decrease"

        # Increase options should have direction "increase"
        assert result.options["3"].direction == "increase"
        assert result.options["4"].direction == "increase"
        assert result.options["5"].direction == "increase"

        # Cleanup
        await character.delete()
        await character_trait.delete()

    async def test_get_value_options_affordability_calculations(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify affordability is correctly calculated for XP and starting points."""
        # Given a character with limited resources
        campaign = await campaign_factory()
        target_user = await user_factory()
        await target_user.add_xp(campaign.id, 10)

        character = await character_factory(
            user_player_id=target_user.id,
            campaign_id=campaign.id,
            starting_points=5,
        )

        trait = await trait_factory(
            initial_cost=1, upgrade_cost=2, max_value=5, min_value=0, is_custom=True
        )
        character_trait = await character_trait_factory(
            character_id=character.id, trait=trait, value=2
        )

        # When we get value options
        service = CharacterTraitService()
        result = await service.get_value_options(
            character=character,
            character_trait=character_trait,
        )

        # Then affordability should be correctly calculated
        # Cost to go from 2 to 3: 3 * 2 = 6 (affordable with 10 XP, but not 5 SP)
        assert result.options["3"].can_use_xp is True
        assert result.options["3"].xp_after == 4
        assert result.options["3"].can_use_starting_points is False
        assert result.options["3"].starting_points_after == -1

        # Downgrades should always be affordable (they refund points)
        assert result.options["1"].can_use_xp is True
        assert result.options["1"].can_use_starting_points is True

        # Cleanup
        await character.delete()
        await character_trait.delete()

    async def test_get_value_options_at_max_value(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify no upgrade options when trait is at max value."""
        # Given a trait at max value
        campaign = await campaign_factory()
        target_user = await user_factory()
        await target_user.add_xp(campaign.id, 100)

        character = await character_factory(
            user_player_id=target_user.id,
            campaign_id=campaign.id,
        )

        trait = await trait_factory(
            initial_cost=1, upgrade_cost=2, max_value=5, min_value=0, is_custom=True
        )
        character_trait = await character_trait_factory(
            character_id=character.id, trait=trait, value=5
        )

        # When we get value options
        service = CharacterTraitService()
        result = await service.get_value_options(
            character=character,
            character_trait=character_trait,
        )

        # Then there should be no increase options, only decrease
        for option in result.options.values():
            assert option.direction == "decrease"

        # Cleanup
        await character.delete()
        await character_trait.delete()

    async def test_get_value_options_at_min_value(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify no downgrade options when trait is at min value."""
        # Given a trait at min value
        campaign = await campaign_factory()
        target_user = await user_factory()
        await target_user.add_xp(campaign.id, 100)

        character = await character_factory(
            user_player_id=target_user.id,
            campaign_id=campaign.id,
        )

        trait = await trait_factory(
            initial_cost=1, upgrade_cost=2, max_value=5, min_value=0, is_custom=True
        )
        character_trait = await character_trait_factory(
            character_id=character.id, trait=trait, value=0
        )

        # When we get value options
        service = CharacterTraitService()
        result = await service.get_value_options(
            character=character,
            character_trait=character_trait,
        )

        # Then there should be no decrease options, only increase (except for DELETE)
        assert "DELETE" in result.options
        for k, v in result.options.items():
            if k == "DELETE":
                assert v.direction == "decrease"
                assert v.point_change == 0
                continue
            assert v.direction == "increase"

        # Cleanup
        await character.delete()
        await character_trait.delete()

    async def test_get_value_options_flaw_trait_inverted(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify get_value_options inverts affordability for flaw traits."""
        # Given a character with a flaw trait and limited resources
        campaign = await campaign_factory()
        target_user = await user_factory()
        await target_user.add_xp(campaign.id, 10)

        character = await character_factory(
            user_player_id=target_user.id,
            campaign_id=campaign.id,
            starting_points=5,
        )

        flaws_category = await TraitCategory.find_one(TraitCategory.name == "Flaws")
        flaw_trait = await trait_factory(
            parent_category_id=flaws_category.id,
            initial_cost=1,
            upgrade_cost=2,
            max_value=5,
            min_value=0,
        )
        character_trait = await character_trait_factory(
            character_id=character.id, trait=flaw_trait, value=2
        )

        # When we get value options
        service = CharacterTraitService()
        result = await service.get_value_options(
            character=character,
            character_trait=character_trait,
        )

        # Then increase options should ALWAYS be affordable (they grant currency)
        assert result.options["3"].can_use_xp is True
        assert result.options["3"].can_use_starting_points is True

        # And increase options should show currency AFTER granting
        # Cost to go from 2 to 3: 3 * 2 = 6
        assert result.options["3"].xp_after == 10 + 6  # 16
        assert result.options["3"].starting_points_after == 5 + 6  # 11

        # Decrease options should check affordability (they cost currency for flaws)
        # Savings from 2 to 1: 2 * 2 = 4 (affordable with 10 XP and 5 SP)
        assert result.options["1"].can_use_xp is True
        assert result.options["1"].xp_after == 10 - 4  # 6
        assert result.options["1"].can_use_starting_points is True
        assert result.options["1"].starting_points_after == 5 - 4  # 1

        # Cleanup
        await character.delete()
        await character_trait.delete()

    async def test_get_value_options_flaw_trait_decrease_unaffordable(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify flaw trait decrease options show unaffordable when not enough currency."""
        # Given a character with a flaw trait and very limited resources
        campaign = await campaign_factory()
        target_user = await user_factory()
        await target_user.add_xp(campaign.id, 2)

        character = await character_factory(
            user_player_id=target_user.id,
            campaign_id=campaign.id,
            starting_points=1,
        )

        flaws_category = await TraitCategory.find_one(TraitCategory.name == "Flaws")
        flaw_trait = await trait_factory(
            parent_category_id=flaws_category.id,
            initial_cost=1,
            upgrade_cost=2,
            max_value=5,
            min_value=0,
        )
        character_trait = await character_trait_factory(
            character_id=character.id, trait=flaw_trait, value=2
        )

        # When we get value options
        service = CharacterTraitService()
        result = await service.get_value_options(
            character=character,
            character_trait=character_trait,
        )

        # Then decrease options should show unaffordable
        # Cost to go from 2 to 1: 2 * 2 = 4
        assert result.options["1"].can_use_xp is False
        assert result.options["1"].xp_after == 2 - 4  # -2
        assert result.options["1"].can_use_starting_points is False
        assert result.options["1"].starting_points_after == 1 - 4  # -3

        # Cleanup
        await character.delete()
        await character_trait.delete()


class TestModifyTraitValue:
    """Test the modify_trait_value method."""

    async def test_modify_trait_value_no_change(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify no change when target equals current value."""
        # Given a character with a trait
        company, user, character = get_company_user_character
        character_trait = await character_trait_factory(value=3, character_id=character.id)

        # When we modify to the same value
        service = CharacterTraitService()
        result = await service.modify_trait_value(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            target_value=3,
            currency="NO_COST",
        )

        # Then the trait value should remain unchanged
        assert result.value == 3

        # Cleanup
        await character_trait.delete()

    async def test_modify_trait_value_increase_no_cost(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        mocker: Any,
    ) -> None:
        """Verify increase with NO_COST calls increase_character_trait_value."""
        # Given a character with a trait
        company, user, character = get_company_user_character
        character_trait = await character_trait_factory(value=2, character_id=character.id)
        spy_increase = mocker.spy(CharacterTraitService, "increase_character_trait_value")

        # When we increase with NO_COST
        service = CharacterTraitService()
        result = await service.modify_trait_value(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            target_value=4,
            currency="NO_COST",
        )

        # Then increase_character_trait_value should be called
        spy_increase.assert_called_once()
        assert result.value == 4

        # Cleanup
        await character_trait.delete()

    async def test_modify_trait_value_decrease_no_cost(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        mocker: Any,
    ) -> None:
        """Verify decrease with NO_COST calls decrease_character_trait_value."""
        # Given a character with a trait
        company, user, character = get_company_user_character
        character_trait = await character_trait_factory(value=4, character_id=character.id)
        spy_decrease = mocker.spy(CharacterTraitService, "decrease_character_trait_value")

        # When we decrease with NO_COST
        service = CharacterTraitService()
        result = await service.modify_trait_value(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            target_value=2,
            currency="NO_COST",
        )

        # Then decrease_character_trait_value should be called
        spy_decrease.assert_called_once()
        assert result.value == 2

        # Cleanup
        await character_trait.delete()

    async def test_modify_trait_value_increase_with_xp(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        company_factory: Callable[[dict[str, ...]], Company],
        mocker: Any,
    ) -> None:
        """Verify increase with XP calls _apply_xp_change."""
        # Given a character with XP
        company = await company_factory()
        campaign = await campaign_factory()
        target_user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        await target_user.add_xp(campaign.id, 100)

        character = await character_factory(
            user_player_id=target_user.id,
            campaign_id=campaign.id,
            company_id=company.id,
        )
        character_trait = await character_trait_factory(value=1, character_id=character.id)
        spy_purchase = mocker.spy(CharacterTraitService, "_apply_xp_change")

        # When we increase with XP
        service = CharacterTraitService()
        result = await service.modify_trait_value(
            company=company,
            user=target_user,
            character=character,
            character_trait=character_trait,
            target_value=2,
            currency="XP",
        )

        # Then _apply_xp_change should be called
        spy_purchase.assert_called_once()
        assert result.value == 2

        # Cleanup
        await character.delete()
        await character_trait.delete()

    async def test_modify_trait_value_decrease_with_xp(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        company_factory: Callable[[dict[str, ...]], Company],
        mocker: Any,
    ) -> None:
        """Verify decrease with XP calls _apply_xp_change."""
        # Given a character
        company = await company_factory()
        campaign = await campaign_factory()
        target_user = await user_factory(company_id=company.id, role=UserRole.ADMIN)

        character = await character_factory(
            user_player_id=target_user.id,
            campaign_id=campaign.id,
            company_id=company.id,
        )
        character_trait = await character_trait_factory(value=3, character_id=character.id)
        spy_refund = mocker.spy(CharacterTraitService, "_apply_xp_change")

        # When we decrease with XP
        service = CharacterTraitService()
        result = await service.modify_trait_value(
            company=company,
            user=target_user,
            character=character,
            character_trait=character_trait,
            target_value=1,
            currency="XP",
        )

        # Then _apply_xp_change should be called
        spy_refund.assert_called_once()
        assert result.value == 1

        # Cleanup
        await character.delete()
        await character_trait.delete()

    async def test_modify_trait_value_increase_with_starting_points(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        mocker: Any,
    ) -> None:
        """Verify increase with STARTING_POINTS calls _apply_starting_points_change."""
        # Given a character with starting points
        company, user, character = get_company_user_character
        character.starting_points = 100
        await character.save()

        character_trait = await character_trait_factory(value=1, character_id=character.id)
        spy_purchase = mocker.spy(CharacterTraitService, "_apply_starting_points_change")

        # When we increase with STARTING_POINTS
        service = CharacterTraitService()
        result = await service.modify_trait_value(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            target_value=2,
            currency="STARTING_POINTS",
        )

        # Then _apply_starting_points_change should be called
        spy_purchase.assert_called_once()
        assert result.value == 2

        # Cleanup
        await character_trait.delete()

    async def test_modify_trait_value_decrease_with_starting_points(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        mocker: Any,
    ) -> None:
        """Verify decrease with STARTING_POINTS calls _apply_starting_points_change."""
        # Given a character
        company, user, character = get_company_user_character
        character_trait = await character_trait_factory(value=3, character_id=character.id)
        spy_refund = mocker.spy(CharacterTraitService, "_apply_starting_points_change")

        # When we decrease with STARTING_POINTS
        service = CharacterTraitService()
        result = await service.modify_trait_value(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            target_value=1,
            currency="STARTING_POINTS",
        )

        # Then _apply_starting_points_change should be called
        spy_refund.assert_called_once()
        assert result.value == 1

        # Cleanup
        await character_trait.delete()


class TestDeleteTrait:
    """Test the delete_trait method."""

    async def test_delete_non_custom_trait_no_currency(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        mocker: Any,
    ) -> None:
        """Verify a non-custom trait is deleted without refund when no currency is provided."""
        # Given a character with a non-custom trait
        company, user, character = get_company_user_character
        character_trait = await character_trait_factory(value=3, character_id=character.id)
        character_trait_id = character_trait.id
        spy_guard = mocker.spy(CharacterTraitService, "guard_user_can_manage_character")
        spy_modify = mocker.spy(CharacterTraitService, "modify_trait_value")

        # When we delete the trait without currency
        service = CharacterTraitService()
        await service.delete_trait(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
        )

        # Then the trait should be deleted and no refund issued
        assert await CharacterTrait.get(character_trait_id) is None
        spy_guard.assert_called_once()
        spy_modify.assert_not_called()

    async def test_delete_non_custom_trait_no_cost_currency(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        mocker: Any,
    ) -> None:
        """Verify NO_COST currency does not trigger a refund."""
        # Given a character with a non-custom trait
        company, user, character = get_company_user_character
        character_trait = await character_trait_factory(value=3, character_id=character.id)
        character_trait_id = character_trait.id
        spy_modify = mocker.spy(CharacterTraitService, "modify_trait_value")

        # When we delete with NO_COST currency
        service = CharacterTraitService()
        await service.delete_trait(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            currency=TraitModifyCurrency.NO_COST,
        )

        # Then the trait should be deleted without refund
        assert await CharacterTrait.get(character_trait_id) is None
        spy_modify.assert_not_called()

    async def test_delete_custom_trait_deletes_trait_definition(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify deleting a custom trait also deletes the Trait definition."""
        # Given a character with a custom trait
        company, user, character = get_company_user_character
        character_trait = await character_trait_factory(
            value=1, character_id=character.id, is_custom=True
        )
        await character_trait.fetch_all_links()
        character_trait_id = character_trait.id
        custom_trait_id = character_trait.trait.id

        # When we delete the custom trait
        service = CharacterTraitService()
        await service.delete_trait(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
        )

        # Then both the CharacterTrait and its Trait definition should be deleted
        assert await CharacterTrait.get(character_trait_id) is None
        assert await Trait.get(custom_trait_id) is None

    async def test_delete_non_custom_trait_preserves_trait_definition(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify deleting a non-custom trait preserves the shared Trait definition."""
        # Given a character with a non-custom trait
        company, user, character = get_company_user_character
        trait = await Trait.find_one(Trait.is_archived == False)
        character_trait = await character_trait_factory(
            value=1, character_id=character.id, trait=trait
        )
        character_trait_id = character_trait.id

        # When we delete the character trait
        service = CharacterTraitService()
        await service.delete_trait(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
        )

        # Then the CharacterTrait is deleted but the Trait definition remains
        assert await CharacterTrait.get(character_trait_id) is None
        assert await Trait.get(trait.id) is not None

    async def test_delete_trait_with_xp_refund(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        company_factory: Callable[[dict[str, ...]], Company],
        mocker: Any,
    ) -> None:
        """Verify deleting with XP currency refunds the trait cost."""
        # Given a character with XP and a trait
        company = await company_factory()
        campaign = await campaign_factory()
        target_user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        await target_user.add_xp(campaign.id, 100)

        character = await character_factory(
            user_player_id=target_user.id,
            campaign_id=campaign.id,
            company_id=company.id,
        )
        character_trait = await character_trait_factory(value=3, character_id=character.id)
        character_trait_id = character_trait.id
        spy_modify = mocker.spy(CharacterTraitService, "modify_trait_value")

        # When we delete with XP refund
        service = CharacterTraitService()
        await service.delete_trait(
            company=company,
            user=target_user,
            character=character,
            character_trait=character_trait,
            currency=TraitModifyCurrency.XP,
        )

        # Then modify_trait_value should be called to refund to value 0
        spy_modify.assert_called_once()
        assert spy_modify.call_args.kwargs["target_value"] == 0
        assert spy_modify.call_args.kwargs["deleting_trait"] is True

        # And the trait should be deleted
        assert await CharacterTrait.get(character_trait_id) is None

        # And XP should be refunded
        await target_user.sync()
        campaign_experience = await target_user.get_or_create_campaign_experience(campaign.id)
        assert campaign_experience.xp_current > 100

        # Cleanup
        await character.delete()

    async def test_delete_trait_with_starting_points_refund(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        mocker: Any,
    ) -> None:
        """Verify deleting with STARTING_POINTS currency refunds the trait cost."""
        # Given a character with starting points and a trait
        company, user, character = get_company_user_character
        character.starting_points = 10
        await character.save()
        initial_starting_points = character.starting_points

        character_trait = await character_trait_factory(value=3, character_id=character.id)
        character_trait_id = character_trait.id
        spy_modify = mocker.spy(CharacterTraitService, "modify_trait_value")

        # When we delete with STARTING_POINTS refund
        service = CharacterTraitService()
        await service.delete_trait(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            currency=TraitModifyCurrency.STARTING_POINTS,
        )

        # Then modify_trait_value should be called to refund to value 0
        spy_modify.assert_called_once()
        assert spy_modify.call_args.kwargs["target_value"] == 0
        assert spy_modify.call_args.kwargs["deleting_trait"] is True

        # And the trait should be deleted
        assert await CharacterTrait.get(character_trait_id) is None

        # And starting points should increase
        await character.sync()
        assert character.starting_points > initial_starting_points

    async def test_delete_trait_permission_denied(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        user_factory: Callable[[dict[str, ...]], User],
        company_factory: Callable[[dict[str, ...]], Company],
    ) -> None:
        """Verify PermissionDeniedError when user doesn't own the character."""
        # Given a character owned by another user
        company = await company_factory()
        owner = await user_factory(role=UserRole.PLAYER)
        character = await character_factory(
            user_player_id=owner.id,
            company_id=company.id,
        )
        character_trait = await character_trait_factory(value=3, character_id=character.id)
        not_owner = await user_factory(role=UserRole.PLAYER)

        # When a non-owner tries to delete
        # Then a PermissionDeniedError should be raised
        service = CharacterTraitService()
        with pytest.raises(PermissionDeniedError, match="User does not own this character"):
            await service.delete_trait(
                company=company,
                user=not_owner,
                character=character,
                character_trait=character_trait,
            )


class TestDeleteCountBasedTrait:
    """Test deleting a count-based trait with count-based cost refund."""

    async def test_delete_gift_with_xp_refunds_count_based_cost(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        company_factory: Callable[[dict[str, ...]], Company],
        user_factory: Callable[[dict[str, ...]], User],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify deleting a gift via XP refunds using count-based pricing."""
        # Given a character with 3 gifts
        company = await company_factory()
        user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        character = await character_factory(
            company_id=company.id, user_player_id=user.id, character_class=CharacterClass.WEREWOLF
        )
        service = CharacterTraitService()

        gift_traits = await Trait.find(
            Trait.gift_attributes != None,
            Trait.is_archived == False,
        ).to_list(3)
        if len(gift_traits) < 3:
            pytest.skip("Not enough gift traits in database")

        for gift_trait in gift_traits:
            await character_trait_factory(character_id=character.id, trait=gift_trait, value=1)

        # Give user some initial XP
        target_user = await GetModelByIdValidationService().get_user_by_id(user.id)
        await target_user.add_xp(character.campaign_id, 50, update_total=True)
        campaign_xp = await target_user.get_or_create_campaign_experience(character.campaign_id)
        xp_before = campaign_xp.xp_current

        # Get the 3rd gift's character_trait to delete
        character_trait = await CharacterTrait.find_one(
            CharacterTrait.character_id == character.id,
            CharacterTrait.trait.id == gift_traits[2].id,
            fetch_links=True,
        )

        # When deleting the gift with XP refund
        await service.delete_trait(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            currency=TraitModifyCurrency.XP,
        )

        # Then XP is refunded by 6 (3rd gift: 3 x 2)
        await target_user.sync()
        campaign_xp = await target_user.get_or_create_campaign_experience(character.campaign_id)
        assert campaign_xp.xp_current == xp_before + 6


class TestBulkAddConstantTraitsToCharacter:
    """Test the bulk_add_constant_traits_to_character method."""

    async def test_all_succeed_no_cost(
        self,
        get_company_user_character: tuple[Company, User, Character],
    ) -> None:
        """Verify all traits succeed when using NO_COST currency."""
        # Given a character and multiple unused traits
        company, user, character = get_company_user_character
        existing_trait_ids = [
            ct.trait.id
            for ct in await CharacterTrait.find(
                CharacterTrait.character_id == character.id, fetch_links=True
            ).to_list()
        ]

        traits = await Trait.find(
            Trait.is_archived == False,
            Not(In(Trait.id, existing_trait_ids)),
        ).to_list()
        test_traits = traits[:3]

        items = [
            CharacterTraitAddConstant(trait_id=t.id, value=1, currency=TraitModifyCurrency.NO_COST)
            for t in test_traits
        ]

        # When bulk assigning traits
        service = CharacterTraitService()
        result = await service.bulk_add_constant_traits_to_character(
            company=company,
            user=user,
            character=character,
            items=items,
        )

        # Then all traits succeed
        assert len(result.succeeded) == 3
        assert len(result.failed) == 0
        for success in result.succeeded:
            assert success.character_trait is not None
            assert success.character_trait.value == 1

    async def test_conflict_trait_already_exists(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify duplicate trait appears in failed list while others succeed."""
        # Given a character with an existing trait
        company, user, character = get_company_user_character
        existing_ct = await character_trait_factory(character_id=character.id)
        await existing_ct.fetch_all_links()
        existing_trait = existing_ct.trait  # type: ignore [attr-defined]
        existing_cts = [existing_ct]

        # And an unused trait
        existing_trait_ids = [ct.trait.id for ct in existing_cts]
        unused_trait = await Trait.find_one(
            Trait.is_archived == False,
            Not(In(Trait.id, existing_trait_ids)),
        )

        items = [
            CharacterTraitAddConstant(
                trait_id=existing_trait.id, value=1, currency=TraitModifyCurrency.NO_COST
            ),
            CharacterTraitAddConstant(
                trait_id=unused_trait.id, value=1, currency=TraitModifyCurrency.NO_COST
            ),
        ]

        # When bulk assigning
        service = CharacterTraitService()
        result = await service.bulk_add_constant_traits_to_character(
            company=company,
            user=user,
            character=character,
            items=items,
        )

        # Then the duplicate fails and the other succeeds
        assert len(result.succeeded) == 1
        assert len(result.failed) == 1
        assert result.failed[0].trait_id == existing_trait.id
        assert "already exists" in result.failed[0].error.lower()

    async def test_validation_failure_value_out_of_bounds(
        self,
        get_company_user_character: tuple[Company, User, Character],
    ) -> None:
        """Verify trait with value exceeding max appears in failed list."""
        # Given a character and an unused trait
        company, user, character = get_company_user_character
        existing_trait_ids = [
            ct.trait.id
            for ct in await CharacterTrait.find(
                CharacterTrait.character_id == character.id, fetch_links=True
            ).to_list()
        ]
        trait = await Trait.find_one(
            Trait.is_archived == False,
            Not(In(Trait.id, existing_trait_ids)),
        )

        items = [
            CharacterTraitAddConstant(
                trait_id=trait.id,
                value=trait.max_value + 1,
                currency=TraitModifyCurrency.NO_COST,
            ),
        ]

        # When bulk assigning with invalid value
        service = CharacterTraitService()
        result = await service.bulk_add_constant_traits_to_character(
            company=company,
            user=user,
            character=character,
            items=items,
        )

        # Then the trait fails validation
        assert len(result.succeeded) == 0
        assert len(result.failed) == 1
        assert "value" in result.failed[0].error.lower()

    async def test_trait_not_found(
        self,
        get_company_user_character: tuple[Company, User, Character],
    ) -> None:
        """Verify non-existent trait_id appears in failed list."""
        # Given a character and a fake trait_id
        company, user, character = get_company_user_character
        fake_id = PydanticObjectId()

        items = [
            CharacterTraitAddConstant(
                trait_id=fake_id, value=1, currency=TraitModifyCurrency.NO_COST
            ),
        ]

        # When bulk assigning with non-existent trait
        service = CharacterTraitService()
        result = await service.bulk_add_constant_traits_to_character(
            company=company,
            user=user,
            character=character,
            items=items,
        )

        # Then the trait fails
        assert len(result.succeeded) == 0
        assert len(result.failed) == 1
        assert "not found" in result.failed[0].error.lower()

    async def test_empty_list(
        self,
        get_company_user_character: tuple[Company, User, Character],
    ) -> None:
        """Verify empty input returns empty succeeded and failed lists."""
        # Given a character and an empty list
        company, user, character = get_company_user_character

        # When bulk assigning nothing
        service = CharacterTraitService()
        result = await service.bulk_add_constant_traits_to_character(
            company=company,
            user=user,
            character=character,
            items=[],
        )

        # Then both lists are empty
        assert len(result.succeeded) == 0
        assert len(result.failed) == 0

    async def test_xp_exhaustion_mid_batch(
        self,
        get_company_user_character: tuple[Company, User, Character],
    ) -> None:
        """Verify later traits fail when XP runs out mid-batch."""
        # Given a character whose user has limited XP
        company, user, character = get_company_user_character
        await user.get_or_create_campaign_experience(character.campaign_id)

        # And multiple unused traits
        existing_trait_ids = [
            ct.trait.id
            for ct in await CharacterTrait.find(
                CharacterTrait.character_id == character.id, fetch_links=True
            ).to_list()
        ]
        traits = await Trait.find(
            Trait.is_archived == False,
            Not(In(Trait.id, existing_trait_ids)),
        ).to_list()

        # Create items that will collectively exceed available XP
        # Use value=1 with XP currency — each costs initial_cost
        items = [
            CharacterTraitAddConstant(trait_id=t.id, value=1, currency=TraitModifyCurrency.XP)
            for t in traits[:10]
        ]

        # When bulk assigning
        service = CharacterTraitService()
        result = await service.bulk_add_constant_traits_to_character(
            company=company,
            user=user,
            character=character,
            items=items,
        )

        # Then some succeed and the rest fail due to insufficient XP
        total = len(result.succeeded) + len(result.failed)
        assert total == 10
        assert len(result.failed) > 0
        for failure in result.failed:
            assert "xp" in failure.error.lower() or "not enough" in failure.error.lower()

    async def test_mixed_currencies_running_balance(
        self,
        get_company_user_character: tuple[Company, User, Character],
    ) -> None:
        """Verify independent running balances for XP and starting points."""
        # Given a character with some XP and starting points
        company, user, character = get_company_user_character

        # And multiple unused traits
        existing_trait_ids = [
            ct.trait.id
            for ct in await CharacterTrait.find(
                CharacterTrait.character_id == character.id, fetch_links=True
            ).to_list()
        ]
        traits = await Trait.find(
            Trait.is_archived == False,
            Not(In(Trait.id, existing_trait_ids)),
        ).to_list()

        # Mix of NO_COST, XP, and STARTING_POINTS
        items = [
            CharacterTraitAddConstant(
                trait_id=traits[0].id, value=1, currency=TraitModifyCurrency.NO_COST
            ),
            CharacterTraitAddConstant(
                trait_id=traits[1].id, value=1, currency=TraitModifyCurrency.XP
            ),
            CharacterTraitAddConstant(
                trait_id=traits[2].id, value=1, currency=TraitModifyCurrency.STARTING_POINTS
            ),
        ]

        # When bulk assigning with mixed currencies
        service = CharacterTraitService()
        result = await service.bulk_add_constant_traits_to_character(
            company=company,
            user=user,
            character=character,
            items=items,
        )

        # Then all items are accounted for (succeeded + failed = total)
        assert len(result.succeeded) + len(result.failed) == 3
        # NO_COST always succeeds
        assert any(s.trait_id == traits[0].id for s in result.succeeded)

    async def test_flaw_trait_increases_running_balance(
        self,
        get_company_user_character: tuple[Company, User, Character],
    ) -> None:
        """Verify flaw trait with XP currency increases running XP balance."""
        # Given a character whose user has limited XP
        company, user, character = get_company_user_character

        # Find a flaw trait (parent category named "Flaws")
        flaws_category = await TraitCategory.find_one(TraitCategory.name == "Flaws")
        existing_trait_ids = [
            ct.trait.id
            for ct in await CharacterTrait.find(
                CharacterTrait.character_id == character.id, fetch_links=True
            ).to_list()
        ]
        flaw_trait = await Trait.find_one(
            Trait.parent_category_id == flaws_category.id,
            Trait.is_archived == False,
            Not(In(Trait.id, existing_trait_ids)),
        )
        normal_trait = await Trait.find_one(
            Trait.parent_category_id != flaws_category.id,
            Trait.is_archived == False,
            Not(In(Trait.id, existing_trait_ids)),
        )

        # Assign flaw first (grants XP), then normal trait (spends XP)
        # Use min_value to satisfy flaw trait's minimum value constraint
        items = [
            CharacterTraitAddConstant(
                trait_id=flaw_trait.id,
                value=flaw_trait.min_value,
                currency=TraitModifyCurrency.XP,
            ),
            CharacterTraitAddConstant(
                trait_id=normal_trait.id, value=1, currency=TraitModifyCurrency.XP
            ),
        ]

        # When bulk assigning
        service = CharacterTraitService()
        result = await service.bulk_add_constant_traits_to_character(
            company=company,
            user=user,
            character=character,
            items=items,
        )

        # Then flaw trait succeeds (grants XP to running balance)
        assert any(s.trait_id == flaw_trait.id for s in result.succeeded)
        # And both items are accounted for
        assert len(result.succeeded) + len(result.failed) == 2

    async def test_bulk_gift_insufficient_renown_fails(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        user_factory: Callable[[dict[str, ...]], User],
        company_factory: Callable[[dict[str, ...]], Company],
    ) -> None:
        """Verify a gift with insufficient renown appears in failed list during bulk add."""
        # Given a werewolf character with total_renown=0
        company = await company_factory()
        campaign = await campaign_factory()
        user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        character = await character_factory(
            user_player_id=user.id,
            campaign_id=campaign.id,
            company_id=company.id,
            character_class=CharacterClass.WEREWOLF,
        )
        assert character.werewolf_attributes.total_renown == 0

        # Given a gift trait with minimum_renown > 0 and a non-gift trait
        gift_trait = await Trait.find_one(
            Trait.gift_attributes != None,
            Trait.gift_attributes.minimum_renown != None,
            Trait.gift_attributes.minimum_renown > 0,
            Trait.is_archived == False,
        )
        non_gift_trait = await Trait.find_one(
            Trait.gift_attributes == None,
            Trait.is_archived == False,
        )
        if gift_trait is None:
            pytest.skip("No gift with minimum_renown found in database")
        if non_gift_trait is None:
            pytest.skip("No non-gift trait found in database")

        items = [
            CharacterTraitAddConstant(
                trait_id=gift_trait.id, value=1, currency=TraitModifyCurrency.XP
            ),
            CharacterTraitAddConstant(
                trait_id=non_gift_trait.id, value=1, currency=TraitModifyCurrency.NO_COST
            ),
        ]

        # When bulk assigning
        service = CharacterTraitService()
        result = await service.bulk_add_constant_traits_to_character(
            company=company,
            user=user,
            character=character,
            items=items,
        )

        # Then the gift fails and the non-gift succeeds
        assert len(result.failed) == 1
        assert result.failed[0].trait_id == gift_trait.id
        assert "Renown" in result.failed[0].error
        assert len(result.succeeded) == 1
        assert result.succeeded[0].character_trait.trait.id == non_gift_trait.id


class TestAddCountBasedTraitToCharacter:
    """Test adding count-based traits through the full add_constant_trait_to_character flow."""

    async def test_add_gift_via_xp_charges_count_based_cost(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        company_factory: Callable[[dict[str, ...]], Company],
        user_factory: Callable[[dict[str, ...]], User],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify adding a gift via XP deducts count-based cost from XP."""
        # Given a werewolf character with 2 existing gifts and some XP
        company = await company_factory()
        campaign = await campaign_factory()
        user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        character = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            character_class=CharacterClass.WEREWOLF,
        )
        service = CharacterTraitService()

        gift_traits = await Trait.find(
            Trait.gift_attributes != None,
            Trait.gift_attributes.minimum_renown != None,
            Trait.gift_attributes.minimum_renown > 0,
            Trait.is_archived == False,
        ).to_list(3)
        if len(gift_traits) < 3:
            pytest.skip("Not enough gift traits with minimum_renown in database")

        # Set renown high enough to satisfy the most demanding gift's requirement
        max_renown = max(t.gift_attributes.minimum_renown for t in gift_traits)
        character.werewolf_attributes.total_renown = max_renown + 1
        await character.save()

        for i in range(2):
            await character_trait_factory(character_id=character.id, trait=gift_traits[i], value=1)

        target_user = await GetModelByIdValidationService().get_user_by_id(user.id)
        await target_user.add_xp(campaign.id, 50, update_total=True)
        campaign_xp = await target_user.get_or_create_campaign_experience(campaign.id)
        xp_before = campaign_xp.xp_current

        # When adding a 3rd gift via XP
        await service.add_constant_trait_to_character(
            company=company,
            character=character,
            user=user,
            trait_id=gift_traits[2].id,
            value=1,
            currency=TraitModifyCurrency.XP,
        )

        # Then XP is reduced by 6 (3rd gift: 3 x 2)
        await target_user.sync()
        campaign_xp = await target_user.get_or_create_campaign_experience(campaign.id)
        assert campaign_xp.xp_current == xp_before - 6

    async def test_add_gift_via_starting_points_charges_count_based_cost(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        company_factory: Callable[[dict[str, ...]], Company],
        user_factory: Callable[[dict[str, ...]], User],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify adding a gift via starting points deducts count-based cost."""
        # Given a werewolf character with 1 existing gift and starting points
        company = await company_factory()
        campaign = await campaign_factory()
        user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        character = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            character_class=CharacterClass.WEREWOLF,
            starting_points=50,
        )
        service = CharacterTraitService()

        gift_traits = await Trait.find(
            Trait.gift_attributes != None,
            Trait.gift_attributes.minimum_renown != None,
            Trait.gift_attributes.minimum_renown > 0,
            Trait.is_archived == False,
        ).to_list(2)
        if len(gift_traits) < 2:
            pytest.skip("Not enough gift traits with minimum_renown in database")

        # Set renown high enough to satisfy the most demanding gift's requirement
        max_renown = max(t.gift_attributes.minimum_renown for t in gift_traits)
        character.werewolf_attributes.total_renown = max_renown + 1
        await character.save()

        await character_trait_factory(character_id=character.id, trait=gift_traits[0], value=1)
        sp_before = character.starting_points

        # When adding a 2nd gift via starting points
        await service.add_constant_trait_to_character(
            company=company,
            character=character,
            user=user,
            trait_id=gift_traits[1].id,
            value=1,
            currency=TraitModifyCurrency.STARTING_POINTS,
        )

        # Then starting points reduced by 4 (2nd gift: 2 x 2)
        await character.sync()
        assert character.starting_points == sp_before - 4


class TestBulkAddCountBasedTraits:
    """Test count-based cost tracking in bulk_add_constant_traits_to_character."""

    async def test_bulk_add_three_gifts_incremental_cost(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        company_factory: Callable[[dict[str, ...]], Company],
        user_factory: Callable[[dict[str, ...]], User],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify bulk-adding gifts uses incrementing count so each gift costs more than the last."""
        # Given a werewolf character with 2 existing gifts and enough starting points
        company = await company_factory()
        campaign = await campaign_factory()
        user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        character = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            character_class=CharacterClass.WEREWOLF,
            starting_points=100,
        )

        gift_traits = await Trait.find(
            Trait.gift_attributes != None,
            Trait.gift_attributes.minimum_renown != None,
            Trait.gift_attributes.minimum_renown > 0,
            Trait.is_archived == False,
        ).to_list(5)
        if len(gift_traits) < 5:
            pytest.skip("Not enough gift traits with minimum_renown in database")

        # Set renown high enough for all gifts
        character.werewolf_attributes.total_renown = 100
        await character.save()

        # Add 2 existing gifts so the next 3 are positions 3, 4, 5
        await character_trait_factory(character_id=character.id, trait=gift_traits[0], value=1)
        await character_trait_factory(character_id=character.id, trait=gift_traits[1], value=1)

        sp_before = character.starting_points
        # Costs: 3rd gift=6, 4th gift=8, 5th gift=10 => total=24
        expected_cost = 6 + 8 + 10

        items = [
            CharacterTraitAddConstant(
                trait_id=gift_traits[2].id, value=1, currency=TraitModifyCurrency.STARTING_POINTS
            ),
            CharacterTraitAddConstant(
                trait_id=gift_traits[3].id, value=1, currency=TraitModifyCurrency.STARTING_POINTS
            ),
            CharacterTraitAddConstant(
                trait_id=gift_traits[4].id, value=1, currency=TraitModifyCurrency.STARTING_POINTS
            ),
        ]

        # When bulk-adding 3 gifts
        service = CharacterTraitService()
        result = await service.bulk_add_constant_traits_to_character(
            company=company,
            user=user,
            character=character,
            items=items,
        )

        # Then all 3 succeed and starting points decreased by the incremental total
        assert len(result.succeeded) == 3
        assert len(result.failed) == 0
        await character.sync()
        assert character.starting_points == sp_before - expected_cost

    async def test_bulk_add_no_cost_gifts_increment_count(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        company_factory: Callable[[dict[str, ...]], Company],
        user_factory: Callable[[dict[str, ...]], User],
    ) -> None:
        """Verify NO_COST gifts increment the running count so subsequent XP gifts cost correctly."""
        # Given a werewolf character with no existing gifts and enough XP
        company = await company_factory()
        campaign = await campaign_factory()
        user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        character = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            character_class=CharacterClass.WEREWOLF,
        )

        gift_traits = await Trait.find(
            Trait.gift_attributes != None,
            Trait.gift_attributes.minimum_renown != None,
            Trait.gift_attributes.minimum_renown > 0,
            Trait.is_archived == False,
        ).to_list(3)
        if len(gift_traits) < 3:
            pytest.skip("Not enough gift traits with minimum_renown in database")

        # Set renown high enough for all gifts; NO_COST skips renown guard
        character.werewolf_attributes.total_renown = 100
        await character.save()

        # Add enough XP for the 3rd gift (cost = 3 * 2 = 6)
        target_user = await GetModelByIdValidationService().get_user_by_id(user.id)
        await target_user.add_xp(campaign.id, 50, update_total=True)
        campaign_xp = await target_user.get_or_create_campaign_experience(campaign.id)
        xp_before = campaign_xp.xp_current

        # 2 NO_COST gifts, then 1 XP gift => XP gift is the 3rd gift: cost = 3 * 2 = 6
        items = [
            CharacterTraitAddConstant(
                trait_id=gift_traits[0].id, value=1, currency=TraitModifyCurrency.NO_COST
            ),
            CharacterTraitAddConstant(
                trait_id=gift_traits[1].id, value=1, currency=TraitModifyCurrency.NO_COST
            ),
            CharacterTraitAddConstant(
                trait_id=gift_traits[2].id, value=1, currency=TraitModifyCurrency.XP
            ),
        ]

        # When bulk-adding 2 NO_COST gifts then 1 XP gift
        service = CharacterTraitService()
        result = await service.bulk_add_constant_traits_to_character(
            company=company,
            user=user,
            character=character,
            items=items,
        )

        # Then all 3 succeed and the XP gift cost 6 (3rd gift position)
        assert len(result.succeeded) == 3
        assert len(result.failed) == 0
        target_user = await GetModelByIdValidationService().get_user_by_id(user.id)
        await target_user.sync()
        campaign_xp = await target_user.get_or_create_campaign_experience(campaign.id)
        assert campaign_xp.xp_current == xp_before - 6

    async def test_bulk_add_mixed_gifts_and_non_gifts(
        self,
        character_factory: Callable[[dict[str, ...]], Character],
        campaign_factory: Callable[[dict[str, ...]], Campaign],
        company_factory: Callable[[dict[str, ...]], Company],
        user_factory: Callable[[dict[str, ...]], User],
    ) -> None:
        """Verify gift and non-gift traits are costed independently during a bulk add."""
        # Given a werewolf character with enough starting points
        company = await company_factory()
        campaign = await campaign_factory()
        user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
        character = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            character_class=CharacterClass.WEREWOLF,
            starting_points=100,
        )

        gift_trait = await Trait.find_one(
            Trait.gift_attributes != None,
            Trait.gift_attributes.minimum_renown != None,
            Trait.gift_attributes.minimum_renown > 0,
            Trait.is_archived == False,
        )
        if gift_trait is None:
            pytest.skip("No gift trait with minimum_renown found in database")

        # Find a non-gift trait with known costs; exclude flaws
        flaws_category = await TraitCategory.find_one(TraitCategory.name == "Flaws")
        non_gift_trait = await Trait.find_one(
            Trait.gift_attributes == None,
            Trait.is_archived == False,
            Trait.parent_category_id != flaws_category.id,
        )
        if non_gift_trait is None:
            pytest.skip("No non-gift trait found in database")

        # Set renown high enough
        character.werewolf_attributes.total_renown = 100
        await character.save()

        sp_before = character.starting_points
        # 1st gift costs 1 * 2 = 2; non-gift value=3 costs initial_cost + 2*upgrade_cost + 3*upgrade_cost
        expected_gift_cost = 2
        expected_non_gift_cost = (
            non_gift_trait.initial_cost
            + 2 * non_gift_trait.upgrade_cost
            + 3 * non_gift_trait.upgrade_cost
        )
        expected_total = expected_gift_cost + expected_non_gift_cost

        items = [
            CharacterTraitAddConstant(
                trait_id=gift_trait.id, value=1, currency=TraitModifyCurrency.STARTING_POINTS
            ),
            CharacterTraitAddConstant(
                trait_id=non_gift_trait.id,
                value=3,
                currency=TraitModifyCurrency.STARTING_POINTS,
            ),
        ]

        # When bulk-adding a gift and a non-gift trait
        service = CharacterTraitService()
        result = await service.bulk_add_constant_traits_to_character(
            company=company,
            user=user,
            character=character,
            items=items,
        )

        # Then both succeed and the total cost reflects separate costing
        assert len(result.succeeded) == 2
        assert len(result.failed) == 0
        await character.sync()
        assert character.starting_points == sp_before - expected_total


class TestGetValueOptionsGifts:
    """Test get_value_options for gift traits with count-based costing."""

    async def test_gift_at_value_0_shows_upgrade_cost(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify gift at value=0 shows count-based upgrade cost and DELETE with cost 0."""
        _, _, character = get_company_user_character
        character.character_class = CharacterClass.WEREWOLF
        await character.save()

        service = CharacterTraitService()

        gift_trait = await Trait.find_one(
            Trait.gift_attributes != None,
            Trait.is_archived == False,
        )
        if gift_trait is None:
            pytest.skip("No gift trait in database")

        character_trait = await character_trait_factory(
            character_id=character.id, trait=gift_trait, value=0
        )

        result = await service.get_value_options(
            character=character, character_trait=character_trait
        )

        # Upgrade to 1 should use count-based cost
        assert "1" in result.options
        assert result.options["1"].direction == "increase"
        assert result.options["1"].point_change == 2  # 1st gift: 1 x 2

        # DELETE option with cost 0 (nothing to delete)
        assert "DELETE" in result.options
        assert result.options["DELETE"].point_change == 0

    async def test_gift_at_value_1_shows_delete_cost(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify gift at value=1 (at min_value) shows only DELETE with count-based cost."""
        _, _, character = get_company_user_character
        character.character_class = CharacterClass.WEREWOLF
        await character.save()

        service = CharacterTraitService()

        gift_trait = await Trait.find_one(
            Trait.gift_attributes != None,
            Trait.is_archived == False,
        )
        if gift_trait is None:
            pytest.skip("No gift trait in database")

        character_trait = await character_trait_factory(
            character_id=character.id, trait=gift_trait, value=1
        )

        result = await service.get_value_options(
            character=character, character_trait=character_trait
        )

        # Gift traits in the DB have min_value=1, so at value=1 no numeric downgrade key exists
        # DELETE is always present and uses count-based cost (1st gift: 1 x 2 = 2)
        assert "DELETE" in result.options
        assert result.options["DELETE"].direction == "decrease"
        assert result.options["DELETE"].point_change == 2  # 1 gift: 1 x 2
