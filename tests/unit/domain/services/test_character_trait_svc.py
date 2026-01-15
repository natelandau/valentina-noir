"""Test the character trait service."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY

import pytest
from beanie import PydanticObjectId
from beanie.operators import In, Not

from vapi.constants import PermissionsFreeTraitChanges, UserRole
from vapi.db.models import Campaign, Character, CharacterTrait, Company, Trait, TraitCategory, User
from vapi.domain.controllers.character_trait.dto import CharacterTraitCreateCustomDTO
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
    ) -> None:
        """Verify that the cost to upgrade is correct for the initial cost.

        The max value of the trait is always set to 5
        """
        service = CharacterTraitService()
        trait = await trait_factory(
            initial_cost=initial_cost, upgrade_cost=upgrade_cost, max_value=5, is_custom=True
        )

        character_trait = CharacterTrait(
            character_id=PydanticObjectId(),
            trait=trait,
            value=current_value,
        )
        assert await service.calculate_upgrade_cost(character_trait, increase_by) == expected

        # cleanup non-constant trait
        await trait.delete()

    async def test_calculate_upgrade_cost_over_max_value(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify that a validation error is raised if the trait is raised above the max value."""
        service = CharacterTraitService()
        trait = await trait_factory(max_value=5, is_custom=True)
        character_trait = CharacterTrait(
            character_id=PydanticObjectId(),
            trait=trait,
            value=4,
        )

        with pytest.raises(ValidationError):
            await service.calculate_upgrade_cost(character_trait, 2)

        # cleanup non-constant trait
        await trait.delete()


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
        character_trait = CharacterTrait(
            character_id=PydanticObjectId(),
            trait=trait,
            value=current_value,
        )
        assert await service.calculate_downgrade_savings(character_trait, decrease_by) == expected

        # cleanup non-constant trait
        await trait.delete()

    async def test_calculate_downgrade_savings_below_min_value(
        self,
        trait_factory: Callable[[dict[str, ...]], Trait],
    ) -> None:
        """Verify that a validation error is raised if the trait is lowered below the min value."""
        service = CharacterTraitService()
        trait = await trait_factory(min_value=0, is_custom=True)
        character_trait = CharacterTrait(
            character_id=PydanticObjectId(),
            trait=trait,
            value=1,
        )
        with pytest.raises(ValidationError):
            await service.calculate_downgrade_savings(character_trait, 3)

        # cleanup non-constant trait
        await trait.delete()


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

        composure_trait = await Trait.find_one(Trait.name == "Composure")
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
        assert willpower.value == 3  # Only Composure, no Resolve yet

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

    async def test_add_constant_trait_to_character(
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

    async def test_add_constant_trait_to_character_idempotent(
        self,
        get_company_user_character: tuple[Company, User, Character],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
    ) -> None:
        """Verify the trait is added to the character."""
        # Given a character and trait
        company, user, character = get_company_user_character
        trait = await Trait.find_one(Trait.is_archived == False)
        pre_existing_trait = await character_trait_factory(
            character_id=character.id, trait=trait, value=1
        )

        # When we call add_constant_trait_to_character
        service = CharacterTraitService()
        result = await service.add_constant_trait_to_character(
            company=company,
            user=user,
            character=character,
            trait_id=trait.id,
            value=2,
        )

        # Then the trait should be added to the character
        await character.sync()
        assert result.id in character.character_trait_ids
        assert result.value == 2
        assert result.id == pre_existing_trait.id

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
            )


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

    async def test_create_custom_trait_conflict(
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
        spy_calculate_upgrade_cost = mocker.spy(CharacterTraitService, "calculate_upgrade_cost")

        character = await character_factory(user_player_id=target_user.id, campaign_id=campaign.id)
        character_trait = await character_trait_factory(value=1, character_id=character.id)

        # When we purchase the trait value with xp
        service = CharacterTraitService()
        result = await service.purchase_trait_value_with_xp(
            user=target_user,
            character=character,
            character_trait=character_trait,
            num_dots=1,
        )

        # Then the trait value should be purchased
        await character_trait.sync()
        assert result.value == 2

        spy_get_user_by_id.assert_called_once_with(ANY, target_user.id)
        spyguard_user_can_manage_character.assert_called_once()
        spy_guard_is_safe_increase.assert_called_once_with(ANY, character_trait, 1)
        spy_calculate_upgrade_cost.assert_called_once_with(ANY, character_trait, 1)
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
            await service.purchase_trait_value_with_xp(
                character=character,
                user=target_user,
                character_trait=character_trait,
                num_dots=1,
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
            CharacterTraitService, "calculate_downgrade_savings"
        )
        # Given a character and trait
        campaign = await campaign_factory()
        target_user = await user_factory()
        await target_user.add_xp(campaign.id, 100)

        character = await character_factory(user_player_id=target_user.id, campaign_id=campaign.id)
        character_trait = await character_trait_factory(value=5, character_id=character.id)

        # When we refund the trait value with xp
        service = CharacterTraitService()
        result = await service.refund_trait_value_with_xp(
            character=character,
            user=target_user,
            character_trait=character_trait,
            num_dots=1,
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
        spy_calculate_downgrade_savings.assert_called_once_with(ANY, character_trait, 1)

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
        spy_calculate_upgrade_cost = mocker.spy(CharacterTraitService, "calculate_upgrade_cost")
        spy_after_save = mocker.spy(CharacterTraitService, "after_save")

        # When we purchase the trait value with starting points
        service = CharacterTraitService()
        result = await service.purchase_trait_increase_with_starting_points(
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=1,
        )

        # Then the trait value should be purchased
        await character_trait.sync()
        assert result.value == trait.min_value + 1

        spyguard_user_can_manage_character.assert_called_once()
        spy_guard_is_safe_increase.assert_called_once_with(ANY, character_trait, 1)
        spy_calculate_upgrade_cost.assert_called_once_with(ANY, character_trait, 1)
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
            await service.purchase_trait_increase_with_starting_points(
                user=user,
                character=character,
                character_trait=character_trait,
                num_dots=1,
            )

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
            CharacterTraitService, "calculate_downgrade_savings"
        )

        # When we refund the trait value with starting points
        service = CharacterTraitService()
        result = await service.refund_trait_decrease_with_starting_points(
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=1,
        )

        # Then the trait value should be refunded
        await character_trait.sync()
        assert result.value == 0
        await character.sync()
        assert character.starting_points == 100 + character_trait.trait.initial_cost * 5
        spy_after_save.assert_called_once_with(ANY, result)
        spy_guard_is_safe_decrease.assert_called_once_with(ANY, character_trait, 1)
        spy_calculate_downgrade_savings.assert_called_once_with(ANY, character_trait, 1)
        spyguard_user_can_manage_character.assert_called_once()

        # Cleanup
        await character_trait.delete()
