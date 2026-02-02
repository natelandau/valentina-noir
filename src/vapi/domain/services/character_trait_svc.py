"""Character trait services."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, assert_never

from beanie.operators import In
from pydantic import ValidationError as PydanticValidationError

from vapi.constants import CharacterClass, PermissionsFreeTraitChanges, UserRole
from vapi.db.models import Character, CharacterTrait, Trait
from vapi.lib.exceptions import ConflictError, PermissionDeniedError, ValidationError
from vapi.utils.time import time_now
from vapi.utils.validation import raise_from_pydantic_validation_error

from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from beanie import PydanticObjectId

    from vapi.db.models import Company, User
    from vapi.domain.controllers.character_trait.dto import CharacterTraitCreateCustomDTO


class CharacterTraitService:
    """Service class for CharacterTrait business logic.

    Encapsulates trait operations that can be called explicitly from controllers
    instead of relying on model hooks.
    """

    def _guard_is_safe_increase(self, character_trait: CharacterTrait, increase_by: int) -> None:
        """Check if increasing the trait value is safe.

        Args:
            character_trait: The trait to increase.
            increase_by: The amount to increase the trait by.

        Raises:
            ValidationError: If the trait cannot be raised above max value.
        """
        new_value = character_trait.value + increase_by
        if new_value > character_trait.trait.max_value:  # type: ignore [attr-defined]
            msg = f"Trait can not be raised above max value of {character_trait.trait.max_value}"  # type: ignore [attr-defined]
            raise ValidationError(detail=msg)

    def _guard_is_safe_decrease(self, character_trait: CharacterTrait, decrease_by: int) -> None:
        """Check if decreasing the trait value is safe.

        Args:
            character_trait: The trait to decrease.
            decrease_by: The amount to decrease the trait by.
        """
        new_value = character_trait.value - decrease_by
        if new_value < character_trait.trait.min_value:  # type: ignore [attr-defined]
            msg = f"Trait can not be lowered below min value of {character_trait.trait.min_value}"  # type: ignore [attr-defined]
            raise ValidationError(detail=msg)

    def guard_user_can_manage_character(self, character: Character, user: User) -> bool:
        """Guard to check if the user is able to update traits on the given character.  Users must be a storyteller or admin or the owner of the character.

        Args:
            character: The character to check the permissions for.
            user: The user to check the permissions for.

        Returns:
            True if the user is able to update traits on the given character, False otherwise.

        Raises:
            PermissionDeniedError: If the user does not have permissions to update traits on the given character.
        """
        if character.user_player_id == user.id or user.role in [
            UserRole.STORYTELLER,
            UserRole.ADMIN,
        ]:
            return True
        raise PermissionDeniedError(detail="User does not own this character")

    def _guard_permissions_free_trait_changes(
        self, company: Company, character: Character, user: User
    ) -> bool:
        """Guard to check if the user has permissions to update traits without spending experience points.

        Args:
            company: The company to check the permissions for.
            character: The character to check the permissions for.
            user: The user to check the permissions for.

        Returns:
            True if the user has permissions to update traits without spending experience points, False otherwise.

        Raises:
            PermissionDeniedError: If the user does not have permissions to update traits without spending experience points.
        """
        if user.role in [UserRole.STORYTELLER, UserRole.ADMIN]:
            return True

        match company.settings.permission_free_trait_changes:
            case PermissionsFreeTraitChanges.UNRESTRICTED:
                return True
            case PermissionsFreeTraitChanges.STORYTELLER:
                if user.role in [UserRole.STORYTELLER, UserRole.ADMIN]:
                    return True
            case PermissionsFreeTraitChanges.WITHIN_24_HOURS:
                if character.date_created + timedelta(days=1) > time_now():
                    return True

            case _:
                assert_never(company.settings.permission_free_trait_changes)

        raise PermissionDeniedError(detail="No rights to access this resource")

    async def calculate_all_upgrade_costs(self, character_trait: CharacterTrait) -> dict[int, int]:
        """Calculate the experience cost to upgrade a trait by each possible number of dots.

        Returns an empty dictionary if the trait is at the max value.

        Args:
            character_trait: The trait to calculate the upgrade costs for.

        Returns:
            A dictionary where keys are the number of dots to increase by (1, 2, 3, etc.)
            and values are the total cost to increase by that many dots.
        """
        upgrade_costs: dict[int, int] = {}
        await character_trait.fetch_all_links()
        max_increase = character_trait.trait.max_value - character_trait.value  # type: ignore [attr-defined]
        for num_dots in range(1, max_increase + 1):
            upgrade_costs[num_dots] = await self.calculate_upgrade_cost(character_trait, num_dots)
        return upgrade_costs

    async def calculate_all_downgrade_savings(
        self, character_trait: CharacterTrait
    ) -> dict[int, int]:
        """Calculate the experience savings from downgrading a trait by each possible number of dots.

        Returns an empty dictionary if the trait is at the min value.

        Args:
            character_trait: The trait to calculate the downgrade savings for.

        Returns:
            A dictionary where keys are the number of dots to decrease by (1, 2, 3, etc.)
            and values are the total savings from decreasing by that many dots.
        """
        downgrade_savings: dict[int, int] = {}
        await character_trait.fetch_all_links()
        max_decrease = character_trait.value - character_trait.trait.min_value  # type: ignore [attr-defined]
        for num_dots in range(1, max_decrease + 1):
            downgrade_savings[num_dots] = await self.calculate_downgrade_savings(
                character_trait, num_dots
            )

        return downgrade_savings

    async def calculate_upgrade_cost(
        self, character_trait: CharacterTrait, increase_by: int
    ) -> int:
        """Calculate the experience cost to upgrade a trait.

        Args:
            character_trait: The trait to upgrade.
            increase_by: The amount to increase the trait by.

        Returns:
            The total cost to upgrade the trait.

        Raises:
            ValidationError: If the trait cannot be raised above max value.
        """
        await character_trait.fetch_all_links()
        cost = 0
        new_trait_value = character_trait.value

        for _ in range(increase_by):
            new_trait_value += 1
            if character_trait.trait.max_value < new_trait_value:  # type: ignore [attr-defined]
                msg = (
                    f"Trait can not be raised above max value of {character_trait.trait.max_value}"  # type: ignore [attr-defined]
                )
                raise ValidationError(
                    invalid_parameters=[{"field": "increase amount", "message": msg}]
                )

            if new_trait_value == 1:
                cost += character_trait.trait.initial_cost  # type: ignore [attr-defined]
            else:
                cost += new_trait_value * character_trait.trait.upgrade_cost  # type: ignore [attr-defined]

        return cost

    async def calculate_downgrade_savings(
        self, character_trait: CharacterTrait, decrease_by: int
    ) -> int:
        """Calculate the experience savings from downgrading a trait.

        Args:
            character_trait: The trait to downgrade.
            decrease_by: The amount to decrease the trait by.

        Returns:
            The total savings from downgrading the trait.

        Raises:
            ValidationError: If the trait cannot be lowered below min value.
        """
        await character_trait.fetch_all_links()
        savings = 0
        new_trait_value = character_trait.value

        for _ in range(decrease_by):
            if new_trait_value - 1 < character_trait.trait.min_value:  # type: ignore [attr-defined]
                msg = (
                    f"Trait can not be lowered below min value of {character_trait.trait.min_value}"  # type: ignore [attr-defined]
                )
                raise ValidationError(
                    invalid_parameters=[{"field": "decrease amount", "message": msg}]
                )
            if new_trait_value == 1:
                savings += character_trait.trait.initial_cost  # type: ignore [attr-defined]
            else:
                savings += new_trait_value * character_trait.trait.upgrade_cost  # type: ignore [attr-defined]
            new_trait_value -= 1

        return savings

    async def update_character_willpower(self, character_trait: CharacterTrait) -> None:
        """Update character willpower based on Composure + Resolve.

        Args:
            character_trait: The trait that was just saved (should be Composure or Resolve).
        """
        await character_trait.fetch_all_links()
        if character_trait.trait.name not in ["Composure", "Resolve"]:  # type: ignore [attr-defined]
            return

        total_willpower_value = (
            await CharacterTrait.find(
                CharacterTrait.character_id == character_trait.character_id,
                In(CharacterTrait.trait.name, ["Composure", "Resolve"]),  # type: ignore [attr-defined]
                fetch_links=True,
            ).sum(CharacterTrait.value)
            or 0
        )

        character_willpower = await CharacterTrait.find_one(
            CharacterTrait.character_id == character_trait.character_id,
            CharacterTrait.trait.name == "Willpower",  # type: ignore [attr-defined]
            fetch_links=True,
        )
        if character_willpower:
            character_willpower.value = int(total_willpower_value)
            await character_willpower.save()
        else:
            willpower_trait = await Trait.find_one(Trait.name == "Willpower")
            character_willpower = CharacterTrait(
                value=int(total_willpower_value),
                character_id=character_trait.character_id,
                trait=willpower_trait,
            )
            await character_willpower.insert()
            await self.after_save(character_willpower)

    async def update_werewolf_total_renown(self, character_trait: CharacterTrait) -> None:
        """Update werewolf total renown based on Honor + Wisdom + Glory.

        Args:
            character_trait: The trait that was just saved (should be Honor, Wisdom, or Glory).
        """
        await character_trait.fetch_all_links()
        if character_trait.trait.name not in ["Honor", "Wisdom", "Glory"]:  # type: ignore [attr-defined]
            return

        character = await Character.get(character_trait.character_id)
        if not character or character.character_class != CharacterClass.WEREWOLF:
            return

        total_renown = await CharacterTrait.find(
            CharacterTrait.character_id == character_trait.character_id,
            In(CharacterTrait.trait.name, ["Honor", "Wisdom", "Glory"]),  # type: ignore [attr-defined]
            fetch_links=True,
        ).sum(CharacterTrait.value)

        character.werewolf_attributes.total_renown = int(total_renown) or 0
        await character.save()

    async def after_save(self, character_trait: CharacterTrait) -> None:
        """Perform all post-save operations for a trait.

        Args:
            character_trait: The trait that was saved.
        """
        await self.update_character_willpower(character_trait)
        await self.update_werewolf_total_renown(character_trait)

    async def add_constant_trait_to_character(
        self,
        *,
        company: Company,
        character: Character,
        user: User,
        trait_id: PydanticObjectId,
        value: int,
    ) -> CharacterTrait:
        """Add a constant trait to a character.

        Args:
            company: The company to check the permissions for.
            character: The character to add the trait to.
            user: The user adding the trait.
            trait_id: The ID of the trait to add.
            value: The value to add to the trait.

        Returns:
            The character trait that was added.
        """
        self.guard_user_can_manage_character(character, user)
        self._guard_permissions_free_trait_changes(company, character, user)

        trait = await GetModelByIdValidationService().get_trait_by_id(trait_id)

        # Idempotent operation - if the trait already exists, update the value
        pre_existing_trait = await CharacterTrait.find_one(
            CharacterTrait.character_id == character.id,
            CharacterTrait.trait.id == trait_id,  # type: ignore [attr-defined]
            fetch_links=True,
        )
        if pre_existing_trait:
            pre_existing_trait.value = value
            await pre_existing_trait.save()
            await self.after_save(pre_existing_trait)
            return pre_existing_trait

        if value > trait.max_value:
            msg = f"Value must be less than or equal to {trait.max_value}"
            raise ValidationError(
                detail=msg, invalid_parameters=[{"field": "value", "message": msg}]
            )

        if value < trait.min_value:
            msg = f"Value must be greater than or equal to {trait.min_value}"
            raise ValidationError(
                detail=msg, invalid_parameters=[{"field": "value", "message": msg}]
            )

        character_trait = CharacterTrait(
            character_id=character.id,
            trait=trait,
            value=value,
        )
        await character_trait.save()
        await self.after_save(character_trait)
        return character_trait

    async def create_custom_trait(
        self,
        *,
        company: Company,
        character: Character,
        user: User,
        data: CharacterTraitCreateCustomDTO,
    ) -> CharacterTrait:
        """Create a custom trait and add it to a character.

        Args:
            company: The company to check the permissions for.
            character: The character to create the trait for.
            user: The user creating the trait.
            data: The data to create the trait with.

        Returns:
            The character trait that was created.

        Raises:
            ConflictError: If the trait already exists on the character.
            ValidationError: If the trait cannot be created.
        """
        self.guard_user_can_manage_character(character, user)
        self._guard_permissions_free_trait_changes(company, character, user)

        all_character_traits = await CharacterTrait.find(
            CharacterTrait.character_id == character.id,
            fetch_links=True,
        ).to_list()
        if data.name.lower() in [trait.trait.name.lower() for trait in all_character_traits]:  # type: ignore [attr-defined]
            raise ConflictError(detail=f"Trait named '{data.name}' already exists on character")

        parent_category = await GetModelByIdValidationService().get_trait_category_by_id(
            data.parent_category_id
        )

        data.initial_cost = data.initial_cost or parent_category.initial_cost
        data.upgrade_cost = data.upgrade_cost or parent_category.upgrade_cost

        try:
            custom_trait = Trait(
                **data.model_dump(exclude_unset=True),
                custom_for_character_id=character.id,
                is_custom=True,
            )
            await custom_trait.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        character_trait = CharacterTrait(
            character_id=character.id,
            trait=custom_trait,
            value=data.value or data.min_value,
        )
        await character_trait.save()

        await self.after_save(character_trait)
        return character_trait

    async def increase_character_trait_value(
        self,
        *,
        company: Company,
        character: Character,
        user: User,
        character_trait: CharacterTrait,
        num_dots: int,
    ) -> CharacterTrait:
        """Increase a character trait value.

        Args:
            company: The company to check the permissions for.
            character: The character to increase the trait for.
            user: The user increasing the trait.
            character_trait: The trait to increase.
            num_dots: The amount to increase the trait by.

        Returns:
            The character trait that was increased.
        """
        self.guard_user_can_manage_character(character, user)
        self._guard_permissions_free_trait_changes(company, character, user)
        self._guard_is_safe_increase(character_trait, num_dots)

        character_trait.value += num_dots
        await character_trait.save()
        await self.after_save(character_trait)
        return character_trait

    async def decrease_character_trait_value(
        self,
        *,
        company: Company,
        character: Character,
        user: User,
        character_trait: CharacterTrait,
        num_dots: int,
    ) -> CharacterTrait:
        """Decrease a character trait value.

        Args:
            company: The company to check the permissions for.
            character: The character to decrease the trait for.
            user: The user decreasing the trait.
            character_trait: The trait to decrease.
            num_dots: The amount to decrease the trait by.

        Returns:
            The character trait that was decreased.

        Raises:
            PermissionDeniedError: If the user does not have permissions to decrease the trait.
            ValidationError: If the trait cannot be lowered below min value.
        """
        self.guard_user_can_manage_character(character, user)
        self._guard_permissions_free_trait_changes(company, character, user)
        self._guard_is_safe_decrease(character_trait, num_dots)

        character_trait.value -= num_dots
        await character_trait.save()
        await self.after_save(character_trait)
        return character_trait

    async def purchase_trait_value_with_xp(
        self,
        *,
        character: Character,
        user: User,
        character_trait: CharacterTrait,
        num_dots: int,
    ) -> CharacterTrait:
        """Purchase a character trait value with xp.

        Args:
            character: The character to purchase the trait for.
            user: The user purchasing the trait.
            character_trait: The trait to purchase.
            num_dots: The amount to purchase the trait by.

        Returns:
            The character trait that was purchased.
        """
        self.guard_user_can_manage_character(character, user)
        self._guard_is_safe_increase(character_trait, num_dots)

        cost = await self.calculate_upgrade_cost(character_trait, num_dots)
        target_user = await GetModelByIdValidationService().get_user_by_id(character.user_player_id)

        await target_user.spend_xp(character.campaign_id, cost)

        character_trait.value += num_dots
        await character_trait.save()
        await self.after_save(character_trait)
        return character_trait

    async def refund_trait_value_with_xp(
        self,
        *,
        character: Character,
        user: User,
        character_trait: CharacterTrait,
        num_dots: int,
    ) -> CharacterTrait:
        """Refund a character trait value with xp.

        Args:
            character: The character to refund the trait for.
            user: The user refunding the trait.
            character_trait: The trait to refund.
            num_dots: The amount to refund the trait by.

        Returns:
            The character trait that was refunded.

        Raises:
            PermissionDeniedError: If the user does not have permissions to refund the trait.
            ValidationError: If the trait cannot be refunded below min value.
        """
        self.guard_user_can_manage_character(character, user)
        self._guard_is_safe_decrease(character_trait, num_dots)
        savings = await self.calculate_downgrade_savings(character_trait, num_dots)
        target_user = await GetModelByIdValidationService().get_user_by_id(character.user_player_id)
        await target_user.add_xp(character.campaign_id, savings, update_total=False)

        character_trait.value -= num_dots
        await character_trait.save()
        await self.after_save(character_trait)
        return character_trait

    async def purchase_trait_increase_with_starting_points(
        self, *, user: User, character: Character, character_trait: CharacterTrait, num_dots: int
    ) -> CharacterTrait:
        """Purchase a character trait value with starting points.

        Args:
            user: The user purchasing the trait.
            character: The character to purchase the trait for.
            character_trait: The trait to purchase.
            num_dots: The amount to purchase the trait by.

        Returns:
            The character trait that was purchased.

        Raises:
            PermissionDeniedError: If the user does not have permissions to purchase the trait.
            ValidationError: If the trait cannot be purchased above max value.
        """
        self.guard_user_can_manage_character(character, user)
        self._guard_is_safe_increase(character_trait, num_dots)

        cost = await self.calculate_upgrade_cost(character_trait, num_dots)
        if character.starting_points < cost:
            raise ValidationError(detail="Not enough starting points")

        character.starting_points -= cost
        await character.save()

        character_trait.value += num_dots
        await character_trait.save()
        await self.after_save(character_trait)
        return character_trait

    async def refund_trait_decrease_with_starting_points(
        self, *, user: User, character: Character, character_trait: CharacterTrait, num_dots: int
    ) -> CharacterTrait:
        """Refund a character trait value with starting points.

        Args:
            user: The user refunding the trait.
            character: The character to refund the trait for.
            character_trait: The trait to refund.
            num_dots: The amount to refund the trait by.

        Returns:
            The character trait that was refunded.

        Raises:
            PermissionDeniedError: If the user does not have permissions to refund the trait.
            ValidationError: If the trait cannot be refunded below min value.
        """
        self.guard_user_can_manage_character(character, user)
        self._guard_is_safe_decrease(character_trait, num_dots)

        savings = await self.calculate_downgrade_savings(character_trait, num_dots)
        character.starting_points += savings
        await character.save()

        character_trait.value -= num_dots
        await character_trait.save()
        await self.after_save(character_trait)
        return character_trait

    async def list_character_traits(
        self,
        character: Character,
        limit: int = 10,
        offset: int = 0,
        parent_category_id: PydanticObjectId | None = None,
    ) -> tuple[int, list[CharacterTrait]]:
        """List all character traits.

        Args:
            character: The character to list the traits for.
            limit: The limit of traits to return.
            offset: The offset of the traits to return.
            parent_category_id: The parent category id to filter the traits by.
        """
        filters = [CharacterTrait.character_id == character.id]

        if parent_category_id:
            filters.append(CharacterTrait.trait.parent_category_id == parent_category_id)  # type: ignore [attr-defined]

        count = await CharacterTrait.find(*filters, fetch_links=True).count()
        traits = (
            await CharacterTrait.find(*filters, fetch_links=True)
            .sort(CharacterTrait.trait.parent_category_id)  # type: ignore [attr-defined]
            .skip(offset)
            .limit(limit)
            .to_list()
        )
        return count, traits
