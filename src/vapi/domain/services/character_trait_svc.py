"""Character trait services."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, assert_never

from beanie.operators import In
from pydantic import ValidationError as PydanticValidationError

from vapi.constants import (
    TRAIT_NAMES_FOR_WILLPOWER,
    CharacterClass,
    PermissionsFreeTraitChanges,
    TraitModifyCurrency,
    UserRole,
)
from vapi.db.models import Character, CharacterTrait, Trait, TraitCategory
from vapi.domain.controllers.character_trait.dto import (
    BulkAssignTraitFailure,
    BulkAssignTraitResponse,
    BulkAssignTraitSuccess,
    CharacterTraitAddConstant,
    CharacterTraitCreateCustomDTO,
    TraitValueOptionDetail,
    TraitValueOptionsResponse,
)
from vapi.lib.exceptions import (
    ConflictError,
    NotEnoughXPError,
    PermissionDeniedError,
    ValidationError,
)
from vapi.utils.time import time_now
from vapi.utils.validation import raise_from_pydantic_validation_error

from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from beanie import PydanticObjectId

    from vapi.db.models import Company, User


class CharacterTraitService:
    """Service class for CharacterTrait business logic.

    Encapsulates trait operations that can be called explicitly from controllers
    instead of relying on model hooks.
    """

    _flaws_category_id: PydanticObjectId | None = None
    _gift_trait_ids: list[PydanticObjectId] | None = None

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

    def _guard_has_minimum_renown(self, trait: Trait, character: Character) -> None:
        """Check if the character meets the minimum renown required for a gift.

        Args:
            trait: The trait being added.
            character: The character to check renown for.

        Raises:
            ValidationError: If the character's renown is below the gift's minimum requirement.
        """
        if trait.gift_attributes is None:
            return
        if trait.gift_attributes.minimum_renown is None:
            return

        total_renown = character.werewolf_attributes.total_renown
        if total_renown < trait.gift_attributes.minimum_renown:
            msg = (
                f"Character's Renown ({total_renown}) does not meet the minimum "
                f"required ({trait.gift_attributes.minimum_renown}) for gift '{trait.name}'"
            )
            raise ValidationError(
                detail=msg,
                invalid_parameters=[{"field": "trait_id", "message": msg}],
            )

    def _cost_for_dot(self, character_trait: CharacterTrait, dot_value: int) -> int:
        """Return the cost for a single dot at the given value.

        Args:
            character_trait: The trait (links must be fetched).
            dot_value: The dot position (1-based).

        Returns:
            The cost for that dot: initial_cost for dot 1, dot_value * upgrade_cost otherwise.
        """
        if dot_value == 1:
            return character_trait.trait.initial_cost  # type: ignore [attr-defined]
        return dot_value * character_trait.trait.upgrade_cost  # type: ignore [attr-defined]

    def _cost_for_gift(self, gift_position: int) -> int:
        """Return the cost for the Nth gift: position * 2."""
        return gift_position * 2

    async def _count_character_gifts(self, character_id: PydanticObjectId) -> int:
        """Count how many active gifts a character currently has.

        Caches the set of gift trait IDs at the class level (gift traits are
        reference data that does not change at runtime), then counts matching
        CharacterTrait records with value > 0.

        Args:
            character_id: The character to count gifts for.

        Returns:
            The number of gift traits the character has with value > 0.
        """
        if CharacterTraitService._gift_trait_ids is None:
            gift_traits = await Trait.find(Trait.gift_attributes != None).to_list()
            CharacterTraitService._gift_trait_ids = [t.id for t in gift_traits]

        if not CharacterTraitService._gift_trait_ids:
            return 0

        return await CharacterTrait.find(
            CharacterTrait.character_id == character_id,
            In(CharacterTrait.trait.id, CharacterTraitService._gift_trait_ids),  # type: ignore [attr-defined]
            CharacterTrait.value > 0,
        ).count()

    async def _is_flaw_trait(self, character_trait: CharacterTrait) -> bool:
        """Check if the trait is a flaw based on its parent category.

        Flaw traits have reversed XP/starting points economy: adding a flaw grants
        currency, removing a flaw costs currency. Links must be fetched before calling.

        Uses a class-level cache for the "Flaws" TraitCategory ID to avoid repeated
        database lookups.

        Args:
            character_trait: The character trait to check.

        Returns:
            True if the trait belongs to the "Flaws" parent category.
        """
        if CharacterTraitService._flaws_category_id is None:
            flaws_category = await TraitCategory.find_one(TraitCategory.name == "Flaws")
            if flaws_category is None:
                return False
            CharacterTraitService._flaws_category_id = flaws_category.id

        return character_trait.trait.parent_category_id == CharacterTraitService._flaws_category_id  # type: ignore [attr-defined]

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
                pass
            case PermissionsFreeTraitChanges.WITHIN_24_HOURS:
                if character.date_created + timedelta(days=1) > time_now():
                    return True
            case _:
                assert_never(company.settings.permission_free_trait_changes)

        raise PermissionDeniedError(detail="No rights to access this resource")

    async def calculate_all_upgrade_costs(self, character_trait: CharacterTrait) -> dict[str, int]:
        """Calculate the experience cost to upgrade a trait by each possible number of dots.

        Returns an empty dictionary if the trait is at the max value.

        Args:
            character_trait: The trait to calculate the upgrade costs for.

        Returns:
            A dictionary where keys are the number of dots to increase by (1, 2, 3, etc.)
            and values are the total cost to increase by that many dots.
        """
        upgrade_costs: dict[str, int] = {}
        await character_trait.fetch_all_links()
        max_increase = character_trait.trait.max_value - character_trait.value  # type: ignore [attr-defined]

        # Pre-fetch gift count once so the loop doesn't re-query per iteration
        gift_count: int | None = None
        if character_trait.trait.gift_attributes is not None:  # type: ignore [attr-defined]
            gift_count = await self._count_character_gifts(character_trait.character_id)

        for num_dots in range(1, max_increase + 1):
            upgrade_costs[str(num_dots)] = await self._calculate_upgrade_cost(
                character_trait,
                num_dots,
                character_id=character_trait.character_id,
                gift_count_override=gift_count,
            )
        return upgrade_costs

    async def calculate_all_downgrade_savings(
        self, character_trait: CharacterTrait
    ) -> dict[str, int]:
        """Calculate the experience savings from downgrading a trait by each possible number of dots.

        Returns an empty dictionary if the trait is at the min value.

        Args:
            character_trait: The trait to calculate the downgrade savings for.

        Returns:
            A dictionary where keys are the number of dots to decrease by (1, 2, 3, etc.)
            and values are the total savings from decreasing by that many dots.
        """
        downgrade_savings: dict[str, int] = {}
        await character_trait.fetch_all_links()
        max_decrease = character_trait.value - character_trait.trait.min_value  # type: ignore [attr-defined]

        # Pre-fetch gift count once so the loop doesn't re-query per iteration
        gift_count: int | None = None
        if character_trait.trait.gift_attributes is not None:  # type: ignore [attr-defined]
            gift_count = await self._count_character_gifts(character_trait.character_id)

        for num_dots in range(1, max_decrease + 1):
            downgrade_savings[str(num_dots)] = await self._calculate_downgrade_savings(
                character_trait,
                num_dots,
                character_id=character_trait.character_id,
                gift_count_override=gift_count,
            )

        downgrade_savings["DELETE"] = await self._calculate_downgrade_savings(
            character_trait,
            character_trait.value,
            character_id=character_trait.character_id,
            gift_count_override=gift_count,
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
        return await self._calculate_upgrade_cost(
            character_trait, increase_by, character_id=character_trait.character_id
        )

    async def _calculate_upgrade_cost(
        self,
        character_trait: CharacterTrait,
        increase_by: int,
        *,
        character_id: PydanticObjectId,
        gift_count_override: int | None = None,
    ) -> int:
        """Calculate upgrade cost assuming links are already fetched.

        For gift traits, uses count-based pricing (Nth gift costs N * 2).
        For all other traits, uses the existing per-dot model.

        Args:
            character_trait: The trait (links must be fetched).
            increase_by: The number of dots to increase by.
            character_id: The character's ID (needed for gift count query).
            gift_count_override: If provided, use this as the current gift count
                instead of querying the DB. Used by bulk operations.

        Returns:
            The total cost to upgrade.

        Raises:
            ValidationError: If the trait would exceed max value.
        """
        if character_trait.trait.gift_attributes is not None:  # type: ignore [attr-defined]
            if gift_count_override is not None:
                current_count = gift_count_override
            else:
                current_count = await self._count_character_gifts(character_id)
            return self._cost_for_gift(current_count + 1)

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

            cost += self._cost_for_dot(character_trait, new_trait_value)

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
        return await self._calculate_downgrade_savings(
            character_trait, decrease_by, character_id=character_trait.character_id
        )

    async def _calculate_downgrade_savings(
        self,
        character_trait: CharacterTrait,
        decrease_by: int,
        *,
        character_id: PydanticObjectId,
        gift_count_override: int | None = None,
    ) -> int:
        """Calculate downgrade savings assuming links are already fetched.

        For gift traits, uses count-based pricing (Nth gift refunds N x 2).
        For all other traits, uses the existing per-dot model.

        Args:
            character_trait: The trait (links must be fetched).
            decrease_by: The number of dots to decrease by.
            character_id: The character's ID (needed for gift count query).
            gift_count_override: If provided, use this as the current gift count
                instead of querying the DB. Used by bulk operations.

        Returns:
            The total savings from downgrading.

        Raises:
            ValidationError: If the trait would go below zero.
        """
        if character_trait.trait.gift_attributes is not None:  # type: ignore [attr-defined]
            if gift_count_override is not None:
                current_count = gift_count_override
            else:
                current_count = await self._count_character_gifts(character_id)
            return self._cost_for_gift(current_count)

        savings = 0
        new_trait_value = character_trait.value

        for _ in range(decrease_by):
            if new_trait_value - 1 < 0:
                msg = "Trait can not be lowered below zero"
                raise ValidationError(
                    invalid_parameters=[{"field": "decrease amount", "message": msg}]
                )
            savings += self._cost_for_dot(character_trait, new_trait_value)
            new_trait_value -= 1

        return savings

    async def update_character_willpower(self, character_trait: CharacterTrait) -> None:
        """Update character willpower based on Composure + Resolve.

        Args:
            character_trait: The trait that was just saved (should be Composure or Resolve).
        """
        await character_trait.fetch_all_links()
        if character_trait.trait.name not in TRAIT_NAMES_FOR_WILLPOWER:  # type: ignore [attr-defined]
            return

        if character_trait.trait.name in ["Composure", "Resolve"]:  # type: ignore [attr-defined]
            total_willpower_value = (
                await CharacterTrait.find(
                    CharacterTrait.character_id == character_trait.character_id,
                    In(CharacterTrait.trait.name, ["Composure", "Resolve"]),  # type: ignore [attr-defined]
                    fetch_links=True,
                ).sum(CharacterTrait.value)
                or 0
            )

        if character_trait.trait.name == "Courage":  # type: ignore [attr-defined]
            total_willpower_value = character_trait.value

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
        currency: TraitModifyCurrency,
    ) -> CharacterTrait:
        """Add a constant trait to a character.

        Args:
            company: The company to check the permissions for.
            character: The character to add the trait to.
            user: The user adding the trait.
            trait_id: The ID of the trait to add.
            value: The value to add to the trait.
            currency: The currency to use to add the trait.
                NO_COST: No cost
                XP: Spend experience points
                STARTING_POINTS: Spend starting points

        Returns:
            The character trait that was added.

        Raises:
            PermissionDeniedError: If the user does not have permissions to add the trait.
            ValidationError: If the trait cannot be added.
        """
        trait = await GetModelByIdValidationService().get_trait_by_id(trait_id)

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

        # NO_COST allows storytellers to bypass renown requirements
        if currency != TraitModifyCurrency.NO_COST:
            self._guard_has_minimum_renown(trait, character)

        # Idempotent operation - if the trait already exists, update the value
        character_trait = await CharacterTrait.find_one(
            CharacterTrait.character_id == character.id,
            CharacterTrait.trait.id == trait_id,  # type: ignore [attr-defined]
            fetch_links=True,
        )
        if character_trait:
            raise ConflictError(
                detail=f"Trait named '{trait.name}' already exists on character. Use modify trait value instead."
            )
        num_dots = value

        character_trait = CharacterTrait(
            character_id=character.id,
            trait=trait,
            value=0,
        )

        if currency == TraitModifyCurrency.NO_COST:
            return await self.increase_character_trait_value(
                company=company,
                user=user,
                character=character,
                character_trait=character_trait,
                num_dots=num_dots,
            )

        if currency == TraitModifyCurrency.XP:
            return await self._apply_xp_change(
                user=user,
                character=character,
                character_trait=character_trait,
                num_dots=num_dots,
                is_increase=True,
            )

        return await self._apply_starting_points_change(
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=num_dots,
            is_increase=True,
        )

    async def bulk_add_constant_traits_to_character(  # noqa: C901, PLR0912, PLR0915
        self,
        *,
        company: Company,
        character: Character,
        user: User,
        items: list[CharacterTraitAddConstant],
    ) -> BulkAssignTraitResponse:
        """Assign multiple constant traits to a character with best-effort semantics.

        Batch-fetch all trait documents and existing character traits up front for
        efficiency. Process each item individually, reusing existing currency methods.
        Maintain running XP and starting points balances to prevent over-spending
        across the batch. Flaw traits invert currency direction.

        Args:
            company: The company to check permissions for.
            character: The character to add traits to.
            user: The user performing the operation.
            items: Validated trait assignment requests.

        Returns:
            BulkAssignTraitResponse with succeeded and failed lists.
        """
        succeeded: list[BulkAssignTraitSuccess] = []
        failed: list[BulkAssignTraitFailure] = []

        if not items:
            return BulkAssignTraitResponse(succeeded=succeeded, failed=failed)

        # Permission check once for the whole batch
        self.guard_user_can_manage_character(character, user)
        self._guard_permissions_free_trait_changes(company, character, user)

        # Batch-fetch all Trait documents
        trait_ids = [item.trait_id for item in items]
        all_traits = await Trait.find(In(Trait.id, trait_ids)).to_list()
        trait_lookup: dict[PydanticObjectId, Trait] = {t.id: t for t in all_traits}

        # Batch-fetch existing CharacterTraits for conflict detection
        existing_cts = await CharacterTrait.find(
            CharacterTrait.character_id == character.id,
            fetch_links=True,
        ).to_list()
        existing_trait_ids: set[PydanticObjectId] = {
            ct.trait.id  # type: ignore [attr-defined]
            for ct in existing_cts
        }

        # Initialize running balances
        target_user = await GetModelByIdValidationService().get_user_by_id(character.user_player_id)
        campaign_xp = await target_user.get_or_create_campaign_experience(character.campaign_id)
        running_xp = campaign_xp.xp_current
        running_starting_points = character.starting_points
        running_gift_count = await self._count_character_gifts(character.id)

        for item in items:
            trait_id = item.trait_id
            value = item.value
            currency = item.currency

            # Validate trait exists
            trait = trait_lookup.get(trait_id)
            if trait is None:
                failed.append(BulkAssignTraitFailure(trait_id=trait_id, error="Trait not found"))
                continue

            # Validate not already on character
            if trait_id in existing_trait_ids:
                failed.append(
                    BulkAssignTraitFailure(
                        trait_id=trait_id,
                        error=f"Trait named '{trait.name}' already exists on character",
                    )
                )
                continue

            # Validate value bounds
            if value > trait.max_value:
                failed.append(
                    BulkAssignTraitFailure(
                        trait_id=trait_id,
                        error=f"Value must be less than or equal to {trait.max_value}",
                    )
                )
                continue

            if value < trait.min_value:
                failed.append(
                    BulkAssignTraitFailure(
                        trait_id=trait_id,
                        error=f"Value must be greater than or equal to {trait.min_value}",
                    )
                )
                continue

            # Validate minimum renown for gifts (NO_COST allows storyteller bypass)
            if currency != TraitModifyCurrency.NO_COST:
                try:
                    self._guard_has_minimum_renown(trait, character)
                except ValidationError as exc:
                    failed.append(BulkAssignTraitFailure(trait_id=trait_id, error=exc.detail))
                    continue

            # Create the CharacterTrait with value=0 (currency methods handle increment)
            character_trait = CharacterTrait(
                character_id=character.id,
                trait=trait,
                value=0,
            )
            num_dots = value

            try:
                if currency == TraitModifyCurrency.NO_COST:
                    result_ct = await self.increase_character_trait_value(
                        company=company,
                        user=user,
                        character=character,
                        character_trait=character_trait,
                        num_dots=num_dots,
                    )
                elif currency == TraitModifyCurrency.XP:
                    # Pre-check running XP balance
                    await character_trait.fetch_all_links()
                    self._guard_is_safe_increase(character_trait, num_dots)
                    cost = await self._calculate_upgrade_cost(
                        character_trait,
                        num_dots,
                        character_id=character_trait.character_id,
                        gift_count_override=running_gift_count,
                    )
                    is_flaw = await self._is_flaw_trait(character_trait)

                    if not is_flaw and running_xp < cost:
                        failed.append(
                            BulkAssignTraitFailure(
                                trait_id=trait_id,
                                error="Not enough XP to add trait",
                            )
                        )
                        continue

                    result_ct = await self._apply_xp_change(
                        character=character,
                        user=user,
                        character_trait=character_trait,
                        num_dots=num_dots,
                        is_increase=True,
                        gift_count_override=running_gift_count,
                    )

                    # Adjust running balance only after successful apply
                    if is_flaw:
                        running_xp += cost
                    else:
                        running_xp -= cost

                elif currency == TraitModifyCurrency.STARTING_POINTS:
                    # Pre-check running starting points balance
                    await character_trait.fetch_all_links()
                    self._guard_is_safe_increase(character_trait, num_dots)
                    cost = await self._calculate_upgrade_cost(
                        character_trait,
                        num_dots,
                        character_id=character_trait.character_id,
                        gift_count_override=running_gift_count,
                    )
                    is_flaw = await self._is_flaw_trait(character_trait)

                    if not is_flaw and running_starting_points < cost:
                        failed.append(
                            BulkAssignTraitFailure(
                                trait_id=trait_id,
                                error="Not enough starting points to add trait",
                            )
                        )
                        continue

                    result_ct = await self._apply_starting_points_change(
                        user=user,
                        character=character,
                        character_trait=character_trait,
                        num_dots=num_dots,
                        is_increase=True,
                        gift_count_override=running_gift_count,
                    )

                    # Adjust running balance only after successful apply
                    if is_flaw:
                        running_starting_points += cost
                    else:
                        running_starting_points -= cost
                else:
                    assert_never(currency)

                succeeded.append(
                    BulkAssignTraitSuccess(
                        trait_id=trait_id,
                        character_trait=result_ct,
                    )
                )
                # Track the newly added trait to prevent duplicates within the batch
                existing_trait_ids.add(trait_id)
                if trait.gift_attributes is not None:
                    running_gift_count += 1

            except (ValidationError, ConflictError, PermissionDeniedError, NotEnoughXPError) as e:
                failed.append(BulkAssignTraitFailure(trait_id=trait_id, error=str(e)))

        return BulkAssignTraitResponse(succeeded=succeeded, failed=failed)

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

        existing_trait = await Trait.find_one(
            Trait.name == data.name.strip().title(),
            Trait.is_custom == False,
            Trait.is_archived == False,
        )
        if existing_trait:
            raise ConflictError(
                detail=f"Trait named '{data.name}' already exists. Custom traits must have a unique name."
            )

        parent_category = await GetModelByIdValidationService().get_trait_category_by_id(
            data.parent_category_id
        )
        sheet_section = await GetModelByIdValidationService().get_sheet_section_by_id(
            parent_category.parent_sheet_section_id
        )

        data.initial_cost = data.initial_cost or parent_category.initial_cost
        data.upgrade_cost = data.upgrade_cost or parent_category.upgrade_cost

        try:
            custom_trait = Trait(
                **data.model_dump(exclude_unset=True),
                parent_category_name=parent_category.name,
                custom_for_character_id=character.id,
                sheet_section_id=sheet_section.id,
                sheet_section_name=sheet_section.name,
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

    async def _apply_xp_change(
        self,
        *,
        character: Character,
        user: User,
        character_trait: CharacterTrait,
        num_dots: int,
        is_increase: bool,
        deleting_trait: bool = False,
        gift_count_override: int | None = None,
    ) -> CharacterTrait:
        """Apply an XP-based trait change, handling flaw inversion.

        For increases: normal traits spend XP, flaw traits grant XP.
        For decreases: normal traits refund XP, flaw traits spend XP.

        Args:
            character: The character owning the trait.
            user: The user making the change.
            character_trait: The trait to modify.
            num_dots: The number of dots to change.
            is_increase: True for increase, False for decrease.
            deleting_trait: Whether the trait is being deleted.
            gift_count_override: If provided, use this as the current gift count
                instead of querying the DB. Used by bulk operations.

        Returns:
            The updated CharacterTrait.
        """
        self.guard_user_can_manage_character(character, user)
        await character_trait.fetch_all_links()

        cost: int
        if is_increase:
            self._guard_is_safe_increase(character_trait, num_dots)
            cost = await self._calculate_upgrade_cost(
                character_trait,
                num_dots,
                character_id=character_trait.character_id,
                gift_count_override=gift_count_override,
            )
        else:
            if not deleting_trait:
                self._guard_is_safe_decrease(character_trait, num_dots)
            cost = await self._calculate_downgrade_savings(
                character_trait,
                num_dots,
                character_id=character_trait.character_id,
                gift_count_override=gift_count_override,
            )

        target_user = await GetModelByIdValidationService().get_user_by_id(character.user_player_id)
        is_flaw = await self._is_flaw_trait(character_trait)

        # Flaw traits invert the currency direction
        if is_increase == is_flaw:
            await target_user.add_xp(character.campaign_id, cost, update_total=False)
        else:
            await target_user.spend_xp(character.campaign_id, cost)

        character_trait.value += num_dots if is_increase else -num_dots
        await character_trait.save()
        await self.after_save(character_trait)
        return character_trait

    async def _apply_starting_points_change(
        self,
        *,
        user: User,
        character: Character,
        character_trait: CharacterTrait,
        num_dots: int,
        is_increase: bool,
        deleting_trait: bool = False,
        gift_count_override: int | None = None,
    ) -> CharacterTrait:
        """Apply a starting-points-based trait change, handling flaw inversion.

        For increases: normal traits spend starting points, flaw traits grant them.
        For decreases: normal traits refund starting points, flaw traits spend them.

        Args:
            user: The user making the change.
            character: The character owning the trait.
            character_trait: The trait to modify.
            num_dots: The number of dots to change.
            is_increase: True for increase, False for decrease.
            deleting_trait: Whether the trait is being deleted.
            gift_count_override: If provided, use this as the current gift count
                instead of querying the DB. Used by bulk operations.

        Returns:
            The updated CharacterTrait.
        """
        self.guard_user_can_manage_character(character, user)
        await character_trait.fetch_all_links()

        cost: int
        if is_increase:
            self._guard_is_safe_increase(character_trait, num_dots)
            cost = await self._calculate_upgrade_cost(
                character_trait,
                num_dots,
                character_id=character_trait.character_id,
                gift_count_override=gift_count_override,
            )
        else:
            if not deleting_trait:
                self._guard_is_safe_decrease(character_trait, num_dots)
            cost = await self._calculate_downgrade_savings(
                character_trait,
                num_dots,
                character_id=character_trait.character_id,
                gift_count_override=gift_count_override,
            )

        is_flaw = await self._is_flaw_trait(character_trait)

        # Flaw traits invert the currency direction
        if is_increase == is_flaw:
            character.starting_points += cost
        else:
            if character.starting_points < cost:
                raise ValidationError(detail="Not enough starting points")
            character.starting_points -= cost
        await character.save()

        character_trait.value += num_dots if is_increase else -num_dots
        await character_trait.save()
        await self.after_save(character_trait)
        return character_trait

    async def list_character_traits(
        self,
        character: Character,
        limit: int = 10,
        offset: int = 0,
        *,
        parent_category_id: PydanticObjectId | None = None,
        is_rollable: bool | None = None,
    ) -> tuple[int, list[CharacterTrait]]:
        """List all character traits.

        Args:
            character: The character to list the traits for.
            limit: The limit of traits to return.
            offset: The offset of the traits to return.
            parent_category_id: The parent category id to filter the traits by.
            is_rollable: Whether to filter the traits by rollable traits.

        Returns:
            A tuple containing the total number of traits and the list of traits.
        """
        filters = [CharacterTrait.character_id == character.id]
        if is_rollable is not None:
            filters.append(CharacterTrait.trait.is_rollable == is_rollable)  # type: ignore [attr-defined]

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

    async def get_value_options(
        self,
        *,
        character: Character,
        character_trait: CharacterTrait,
    ) -> TraitValueOptionsResponse:
        """Get all possible target values for a trait with costs and affordability.

        For flaw traits, the currency direction is inverted: increases grant currency
        (always affordable) and decreases cost currency (requires affordability check).

        Args:
            character: The character owning the trait.
            character_trait: The trait to get options for.

        Returns:
            A TraitValueOptionsResponse containing current value, min/max bounds, current XP and starting points, and options for each possible target value.
        """
        await character_trait.fetch_all_links()

        target_user = await GetModelByIdValidationService().get_user_by_id(character.user_player_id)
        campaign_experience = await target_user.get_or_create_campaign_experience(
            character.campaign_id
        )

        current_value = character_trait.value
        xp_current = campaign_experience.xp_current
        starting_points_current = character.starting_points
        is_flaw = await self._is_flaw_trait(character_trait)

        upgrade_costs = await self.calculate_all_upgrade_costs(character_trait)
        downgrade_savings = await self.calculate_all_downgrade_savings(character_trait)

        options: dict[str, TraitValueOptionDetail] = {}

        for num_dots_str, cost in upgrade_costs.items():
            num_dots = int(num_dots_str)
            target_value = current_value + num_dots
            # Flaw upgrades grant currency; normal upgrades spend it
            sign = 1 if is_flaw else -1
            xp_after = xp_current + cost * sign
            starting_points_after = starting_points_current + cost * sign

            options[str(target_value)] = TraitValueOptionDetail(
                direction="increase",
                point_change=cost,
                can_use_xp=is_flaw or xp_after >= 0,
                xp_after=xp_after,
                can_use_starting_points=is_flaw or starting_points_after >= 0,
                starting_points_after=starting_points_after,
            )

        for num_dots_str, savings in downgrade_savings.items():
            num_dots = int(num_dots_str) if num_dots_str != "DELETE" else 0
            target_value = current_value - num_dots
            # Flaw downgrades spend currency; normal downgrades grant it
            sign = -1 if is_flaw else 1
            xp_after = xp_current + savings * sign
            starting_points_after = starting_points_current + savings * sign
            key = str(target_value) if num_dots_str != "DELETE" else "DELETE"

            options[key] = TraitValueOptionDetail(
                direction="decrease",
                point_change=savings,
                can_use_xp=not is_flaw or xp_after >= 0,
                xp_after=xp_after,
                can_use_starting_points=not is_flaw or starting_points_after >= 0,
                starting_points_after=starting_points_after,
            )

        return TraitValueOptionsResponse(
            name=character_trait.trait.name,  # type: ignore [attr-defined]
            current_value=current_value,
            trait=character_trait.trait,  # type: ignore [arg-type]
            xp_current=xp_current,
            starting_points_current=starting_points_current,
            options=options,
        )

    async def modify_trait_value(  # noqa: PLR0911, PLR0913
        self,
        *,
        company: Company,
        user: User,
        character: Character,
        character_trait: CharacterTrait,
        target_value: int,
        currency: TraitModifyCurrency,
        deleting_trait: bool = False,
        gift_count_override: int | None = None,
    ) -> CharacterTrait:
        """Modify a trait to a target value using the specified currency.

        Args:
            company: The company to check permissions for.
            user: The user making the modification.
            character: The character owning the trait.
            character_trait: The trait to modify.
            target_value: The desired target value for the trait.
            currency: The currency to use (NO_COST, XP, or STARTING_POINTS).
            deleting_trait: Whether the trait is being deleted.
            gift_count_override: If provided, use this as the current gift count
                instead of querying the DB. Used by bulk operations.

        Returns:
            The updated CharacterTrait.

        Raises:
            ValidationError: If the target value is invalid or unaffordable.
            PermissionDeniedError: If the user lacks required permissions.
        """
        await character_trait.fetch_all_links()
        current_value = character_trait.value
        num_dots = abs(target_value - current_value)

        if num_dots == 0:
            return character_trait

        is_increase = target_value > current_value

        if is_increase:
            if currency == TraitModifyCurrency.NO_COST:
                return await self.increase_character_trait_value(
                    company=company,
                    user=user,
                    character=character,
                    character_trait=character_trait,
                    num_dots=num_dots,
                )
            if currency == TraitModifyCurrency.XP:
                return await self._apply_xp_change(
                    user=user,
                    character=character,
                    character_trait=character_trait,
                    num_dots=num_dots,
                    is_increase=True,
                    gift_count_override=gift_count_override,
                )
            return await self._apply_starting_points_change(
                user=user,
                character=character,
                character_trait=character_trait,
                num_dots=num_dots,
                is_increase=True,
                gift_count_override=gift_count_override,
            )

        if currency == TraitModifyCurrency.NO_COST:
            return await self.decrease_character_trait_value(
                company=company,
                user=user,
                character=character,
                character_trait=character_trait,
                num_dots=num_dots,
            )
        if currency == TraitModifyCurrency.XP:
            return await self._apply_xp_change(
                user=user,
                character=character,
                character_trait=character_trait,
                num_dots=num_dots,
                is_increase=False,
                deleting_trait=deleting_trait,
                gift_count_override=gift_count_override,
            )
        return await self._apply_starting_points_change(
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=num_dots,
            is_increase=False,
            deleting_trait=deleting_trait,
            gift_count_override=gift_count_override,
        )

    async def delete_trait(
        self,
        *,
        company: Company,
        user: User,
        character: Character,
        character_trait: CharacterTrait,
        currency: TraitModifyCurrency | None = None,
    ) -> None:
        """Delete a trait from a character.

        Args:
            company: The company
            user: The user deleting the trait.
            character: The character to delete the trait from.
            character_trait: The trait to delete.
            currency: The currency to use to recoup the cost of the trait.

        Returns:
            The character trait that was deleted.

        Raises:
            PermissionDeniedError: If the user does not have permissions to delete the trait.
            ValidationError: If the trait cannot be deleted.
        """
        self.guard_user_can_manage_character(character, user)

        if currency and currency != TraitModifyCurrency.NO_COST:
            character_trait = await self.modify_trait_value(
                company=company,
                user=user,
                character=character,
                character_trait=character_trait,
                target_value=0,
                currency=currency,
                deleting_trait=True,
            )

        if character_trait.trait.is_custom:  # type: ignore [attr-defined]
            await character_trait.trait.delete()  # type: ignore [attr-defined]
        await character_trait.delete()
