"""Character trait services."""

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, ClassVar, assert_never
from uuid import UUID

from litestar.stores.base import Store
from tortoise.transactions import in_transaction

from vapi.constants import (
    RECOUP_XP_SESSION_LENGTH,
    CharacterClass,
    PermissionsFreeTraitChanges,
    PermissionsRecoupXP,
    TraitModifyCurrency,
    UserRole,
)
from vapi.db.sql_models.character import Character, CharacterTrait, WerewolfAttributes
from vapi.db.sql_models.character_sheet import Trait, TraitCategory
from vapi.db.sql_models.company import CompanySettings
from vapi.domain.controllers.character_trait.dto import (
    CHARACTER_TRAIT_PREFETCH,
    BulkAssignTraitFailure,
    BulkAssignTraitResponse,
    BulkAssignTraitSuccess,
    CharacterTraitAddConstant,
    CharacterTraitCreateCustom,
    CharacterTraitResponse,
    TraitResponse,
    TraitValueOptionDetail,
    TraitValueOptionsResponse,
)
from vapi.domain.services.user_svc import UserXPService
from vapi.lib.exceptions import (
    ConflictError,
    NotEnoughXPError,
    PermissionDeniedError,
    ValidationError,
)
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.user import User

# Derived-trait sync constants
RENOWN_COMPONENTS = frozenset({"Honor", "Wisdom", "Glory"})


class CharacterTraitService:
    """Service class for CharacterTrait business logic.

    Encapsulates trait operations that can be called explicitly from controllers
    instead of relying on model hooks.
    """

    _flaws_category_id: ClassVar[UUID | None] = None

    def _guard_is_safe_increase(self, character_trait: CharacterTrait, increase_by: int) -> None:
        """Check if increasing the trait value is safe.

        Args:
            character_trait: The trait to increase.
            increase_by: The amount to increase the trait by.

        Raises:
            ValidationError: If the trait cannot be raised above max value.
        """
        new_value = character_trait.value + increase_by
        if new_value > character_trait.trait.max_value:
            msg = f"Trait can not be raised above max value of {character_trait.trait.max_value}"
            raise ValidationError(detail=msg)

    def _guard_is_safe_decrease(self, character_trait: CharacterTrait, decrease_by: int) -> None:
        """Check if decreasing the trait value is safe.

        Args:
            character_trait: The trait to decrease.
            decrease_by: The amount to decrease the trait by.

        Raises:
            ValidationError: If the trait cannot be lowered below min value.
        """
        new_value = character_trait.value - decrease_by
        if new_value < character_trait.trait.min_value:
            msg = f"Trait can not be lowered below min value of {character_trait.trait.min_value}"
            raise ValidationError(detail=msg)

    async def _guard_has_minimum_renown(self, trait: Trait, character: Character) -> None:
        """Check if the character meets the minimum renown required for a gift.

        Args:
            trait: The trait being added.
            character: The character to check renown for.

        Raises:
            ValidationError: If the character's renown is below the gift's minimum requirement.
        """
        if trait.gift_minimum_renown is None:
            return

        werewolf_attrs = await WerewolfAttributes.filter(character_id=character.id).first()
        total_renown = werewolf_attrs.total_renown if werewolf_attrs else 0
        if total_renown < trait.gift_minimum_renown:
            msg = (
                f"Character's Renown ({total_renown}) does not meet the minimum "
                f"required ({trait.gift_minimum_renown}) for gift '{trait.name}'"
            )
            raise ValidationError(
                detail=msg,
                invalid_parameters=[{"field": "trait_id", "message": msg}],
            )

    async def _guard_can_afford_new_trait(
        self,
        trait: Trait,
        character: Character,
        value: int,
        currency: TraitModifyCurrency,
    ) -> None:
        """Check that the character can afford to add a new trait before creating it.

        Computes the upgrade cost from 0 to `value` using the trait's cost fields and
        verifies the character (or user) has enough currency. Flaw traits grant currency
        instead of spending it, so the check is skipped for flaws.

        Args:
            trait: The trait definition being added.
            character: The character receiving the trait.
            value: The target value (number of dots).
            currency: The currency being used (XP or STARTING_POINTS).

        Raises:
            NotEnoughXPError: If the user cannot afford the XP cost.
            ValidationError: If the character cannot afford the starting points cost.
        """
        if await self._is_flaw_category(trait.category_id):  # type: ignore[attr-defined]
            return

        multiplier = trait.count_based_cost_multiplier
        if multiplier is not None:
            count = await self._count_category_traits(character.id, trait.category_id)  # type: ignore[attr-defined]
            cost = (count + 1) * multiplier
        else:
            cost = 0
            for dot in range(1, value + 1):
                cost += self._cost_for_dot_value(trait.initial_cost, trait.upgrade_cost, dot)

        if currency == TraitModifyCurrency.XP:
            user_svc = UserXPService()
            experience = await user_svc.get_or_create_campaign_experience(
                character.user_player_id,  # type: ignore[attr-defined]
                character.campaign_id,  # type: ignore[attr-defined]
            )
            if experience.xp_current < cost:
                raise NotEnoughXPError
        elif currency == TraitModifyCurrency.STARTING_POINTS and character.starting_points < cost:
            raise ValidationError(detail="Not enough starting points")

    @staticmethod
    def _cost_for_dot_value(initial_cost: int, upgrade_cost: int, dot_value: int) -> int:
        """Return the cost for a single dot at the given value.

        Args:
            initial_cost: The cost for the first dot.
            upgrade_cost: The per-dot multiplier for subsequent dots.
            dot_value: The dot position (1-based).

        Returns:
            The cost for that dot: initial_cost for dot 1, dot_value * upgrade_cost otherwise.
        """
        if dot_value == 1:
            return initial_cost
        return dot_value * upgrade_cost

    def _cost_for_dot(self, character_trait: CharacterTrait, dot_value: int) -> int:
        """Return the cost for a single dot at the given value.

        Args:
            character_trait: The trait (must have trait prefetched).
            dot_value: The dot position (1-based).

        Returns:
            The cost for that dot: initial_cost for dot 1, dot_value * upgrade_cost otherwise.
        """
        return self._cost_for_dot_value(
            character_trait.trait.initial_cost, character_trait.trait.upgrade_cost, dot_value
        )

    async def _count_category_traits(self, character_id: UUID, category_id: UUID) -> int:
        """Count how many active traits a character has in a given category.

        Args:
            character_id: The character to count traits for.
            category_id: The category to count traits in.

        Returns:
            The number of traits with value > 0 in the category.
        """
        return await CharacterTrait.filter(
            character_id=character_id,
            trait__category_id=category_id,
            value__gt=0,
        ).count()

    async def _is_flaw_category(self, category_id: UUID) -> bool:
        """Check if a category ID belongs to the "Flaws" category.

        Uses a class-level cache for the "Flaws" TraitCategory ID to avoid repeated
        database lookups.

        Args:
            category_id: The category ID to check.

        Returns:
            True if the category ID matches the "Flaws" category.
        """
        if CharacterTraitService._flaws_category_id is None:
            flaws_category = await TraitCategory.filter(name="Flaws").first()
            if flaws_category is None:
                return False
            CharacterTraitService._flaws_category_id = flaws_category.id

        return category_id == CharacterTraitService._flaws_category_id

    async def _is_flaw_trait(self, character_trait: CharacterTrait) -> bool:
        """Check if the trait is a flaw based on its parent category.

        Flaw traits have reversed XP/starting points economy: adding a flaw grants
        currency, removing a flaw costs currency. Trait must be prefetched before calling.

        Args:
            character_trait: The character trait to check.

        Returns:
            True if the trait belongs to the "Flaws" parent category.
        """
        return await self._is_flaw_category(character_trait.trait.category_id)  # type: ignore[attr-defined]

    def guard_user_can_manage_character(self, character: Character, user: "User") -> bool:
        """Guard to check if the user is able to update traits on the given character.

        Users must be a storyteller or admin or the owner of the character.

        Args:
            character: The character to check the permissions for.
            user: The user to check the permissions for.

        Returns:
            True if the user is able to update traits on the given character.

        Raises:
            PermissionDeniedError: If the user does not have permissions to update traits.
        """
        if character.user_player_id == user.id or user.role in [  # type: ignore[attr-defined]
            UserRole.STORYTELLER,
            UserRole.ADMIN,
        ]:
            return True
        raise PermissionDeniedError(detail="User does not own this character")

    async def _guard_permissions_free_trait_changes(
        self, company: "Company", character: Character, user: "User"
    ) -> bool:
        """Guard to check if the user has permissions to update traits without spending XP.

        Args:
            company: The company to check the permissions for.
            character: The character to check the permissions for.
            user: The user to check the permissions for.

        Returns:
            True if the user has permissions to update traits without spending XP.

        Raises:
            PermissionDeniedError: If the user does not have permissions.
        """
        if user.role in [UserRole.STORYTELLER, UserRole.ADMIN]:
            return True

        settings = await CompanySettings.filter(company_id=company.id).first()
        if settings is None:
            raise PermissionDeniedError(detail="No rights to access this resource")

        match settings.permission_free_trait_changes:
            case PermissionsFreeTraitChanges.UNRESTRICTED:
                return True
            case PermissionsFreeTraitChanges.STORYTELLER:
                pass
            case PermissionsFreeTraitChanges.WITHIN_24_HOURS:
                if character.date_created + timedelta(days=1) > time_now():
                    return True
            case _:
                assert_never(settings.permission_free_trait_changes)

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
        max_increase = character_trait.trait.max_value - character_trait.value

        for num_dots in range(1, max_increase + 1):
            upgrade_costs[str(num_dots)] = await self._calculate_upgrade_cost(
                character_trait,
                num_dots,
                character_id=character_trait.character_id,  # type: ignore[attr-defined]
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
        max_decrease = character_trait.value - character_trait.trait.min_value

        for num_dots in range(1, max_decrease + 1):
            downgrade_savings[str(num_dots)] = await self._calculate_downgrade_savings(
                character_trait,
                num_dots,
                character_id=character_trait.character_id,  # type: ignore[attr-defined]
            )

        downgrade_savings["DELETE"] = await self._calculate_downgrade_savings(
            character_trait,
            character_trait.value,
            character_id=character_trait.character_id,  # type: ignore[attr-defined]
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
        return await self._calculate_upgrade_cost(
            character_trait,
            increase_by,
            character_id=character_trait.character_id,  # type: ignore[attr-defined]
        )

    async def _calculate_upgrade_cost(
        self,
        character_trait: CharacterTrait,
        increase_by: int,
        *,
        character_id: UUID,
    ) -> int:
        """Calculate upgrade cost assuming trait is already prefetched.

        For count-based traits, uses count-based pricing (Nth trait costs N * multiplier).
        For all other traits, uses the existing per-dot model.

        Args:
            character_trait: The trait (must have trait prefetched).
            increase_by: The number of dots to increase by.
            character_id: The character's ID (needed for count query).

        Returns:
            The total cost to upgrade.

        Raises:
            ValidationError: If the trait would exceed max value.
        """
        multiplier = character_trait.trait.count_based_cost_multiplier
        if multiplier is not None:
            if increase_by != 1:
                msg = f"Count-based traits only support single-dot increases, got {increase_by}"
                raise ValidationError(detail=msg)
            count = await self._count_category_traits(
                character_id,
                character_trait.trait.category_id,  # type: ignore[attr-defined]
            )
            return (count + 1) * multiplier

        cost = 0
        new_trait_value = character_trait.value

        for _ in range(increase_by):
            new_trait_value += 1
            if character_trait.trait.max_value < new_trait_value:
                msg = (
                    f"Trait can not be raised above max value of {character_trait.trait.max_value}"
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
        return await self._calculate_downgrade_savings(
            character_trait,
            decrease_by,
            character_id=character_trait.character_id,  # type: ignore[attr-defined]
        )

    async def _calculate_downgrade_savings(
        self,
        character_trait: CharacterTrait,
        decrease_by: int,
        *,
        character_id: UUID,
    ) -> int:
        """Calculate downgrade savings assuming trait is already prefetched.

        For count-based traits, uses count-based pricing (Nth trait refunds N * multiplier).
        For all other traits, uses the existing per-dot model.

        Args:
            character_trait: The trait (must have trait prefetched).
            decrease_by: The number of dots to decrease by.
            character_id: The character's ID (needed for count query).

        Returns:
            The total savings from downgrading.

        Raises:
            ValidationError: If the trait would go below zero.
        """
        multiplier = character_trait.trait.count_based_cost_multiplier
        if multiplier is not None:
            count = await self._count_category_traits(
                character_id,
                character_trait.trait.category_id,  # type: ignore[attr-defined]
            )
            return count * multiplier

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

    async def update_werewolf_total_renown(self, character: Character) -> None:
        """Update werewolf total renown based on Honor + Wisdom + Glory.

        Args:
            character: The character whose renown should be recalculated.
        """
        if character.character_class != CharacterClass.WEREWOLF:
            return

        renown_traits = await CharacterTrait.filter(
            character_id=character.id,
            trait__name__in=list(RENOWN_COMPONENTS),
        ).select_related("trait")

        total_renown = sum(ct.value for ct in renown_traits) if renown_traits else 0

        werewolf_attrs = await WerewolfAttributes.filter(character_id=character.id).first()
        if werewolf_attrs is None:
            return

        werewolf_attrs.total_renown = total_renown
        await werewolf_attrs.save(update_fields=["total_renown", "date_modified"])

    async def after_save(self, character_trait: CharacterTrait, character: Character) -> None:  # noqa: ARG002
        """Perform all post-save operations for a trait.

        Args:
            character_trait: The trait that was saved.
            character: The character that owns the trait.
        """
        await self.update_werewolf_total_renown(character)

    async def _refetch_character_trait(self, character_trait_id: UUID) -> CharacterTrait:
        """Refetch a CharacterTrait with all relations prefetched for response serialization.

        Args:
            character_trait_id: The ID of the CharacterTrait to refetch.

        Returns:
            The CharacterTrait with prefetched relations.
        """
        result = (
            await CharacterTrait.filter(id=character_trait_id)
            .prefetch_related(*CHARACTER_TRAIT_PREFETCH)
            .first()
        )
        if result is None:
            msg = "CharacterTrait not found after save"
            raise ValidationError(detail=msg)
        return result

    @staticmethod
    def _recoup_floor_key(*, user_id: str, character_id: str, trait_id: str) -> str:
        """Build the Redis key for a (user, character, trait) recoup floor."""
        return f"recoup_floor:{user_id}:{character_id}:{trait_id}"

    async def _get_recoup_floor(
        self, *, store: Store, user_id: str, character_id: str, trait_id: str
    ) -> int | None:
        """Read the stored recoup floor for this trait, or None if absent or expired."""
        key = self._recoup_floor_key(user_id=user_id, character_id=character_id, trait_id=trait_id)
        raw = await store.get(key)
        if raw is None:
            return None
        return int(raw.decode("utf-8") if isinstance(raw, bytes) else raw)

    async def _set_recoup_floor(
        self,
        *,
        store: Store,
        user_id: str,
        character_id: str,
        trait_id: str,
        value: int,
    ) -> None:
        """Write a new floor value with the configured session TTL."""
        key = self._recoup_floor_key(user_id=user_id, character_id=character_id, trait_id=trait_id)
        await store.set(key, str(value).encode("utf-8"), expires_in=RECOUP_XP_SESSION_LENGTH)

    async def _enforce_recoup_xp_permission(  # noqa: PLR0913
        self,
        *,
        company: "Company",
        user: "User",
        character: Character,
        character_trait: CharacterTrait,
        current_value: int,
        target_value: int,
        is_increase: bool,
        store: Store,
    ) -> None:
        """Enforce the company's permission_recoup_xp setting for an XP-currency change."""
        # company.settings is prefetched by the DI provider (provide_company_by_id).
        setting = company.settings.permission_recoup_xp
        user_id = str(user.id)
        character_id = str(character.id)
        trait_id = str(character_trait.id)

        match setting:
            case PermissionsRecoupXP.UNRESTRICTED:
                return
            case PermissionsRecoupXP.DENIED:
                if not is_increase:
                    msg = (
                        "Lowering trait values is not permitted for this company. "
                        "Current setting: DENIED."
                    )
                    raise PermissionDeniedError(detail=msg)
                return
            case PermissionsRecoupXP.WITHIN_SESSION:
                if is_increase:
                    existing_floor = await self._get_recoup_floor(
                        store=store,
                        user_id=user_id,
                        character_id=character_id,
                        trait_id=trait_id,
                    )
                    # On the first raise in a session, anchor the floor at the
                    # pre-update value; on subsequent raises, re-write the same
                    # floor to refresh its TTL.
                    floor_to_write = current_value if existing_floor is None else existing_floor
                    await self._set_recoup_floor(
                        store=store,
                        user_id=user_id,
                        character_id=character_id,
                        trait_id=trait_id,
                        value=floor_to_write,
                    )
                    return

                floor = await self._get_recoup_floor(
                    store=store,
                    user_id=user_id,
                    character_id=character_id,
                    trait_id=trait_id,
                )
                if floor is None:
                    msg = (
                        "Lowering trait values is not permitted for this company outside of "
                        "an active edit session. Current setting: WITHIN_SESSION."
                    )
                    raise PermissionDeniedError(detail=msg)
                if target_value < floor:
                    msg = (
                        f"Cannot lower this trait below {floor} (the value at the start of "
                        "your current edit session). Current setting: WITHIN_SESSION."
                    )
                    raise PermissionDeniedError(detail=msg)
                # Successful lower within the session refreshes the floor's TTL.
                await self._set_recoup_floor(
                    store=store,
                    user_id=user_id,
                    character_id=character_id,
                    trait_id=trait_id,
                    value=floor,
                )
                return
            case _ as unreachable:
                assert_never(unreachable)

    async def add_constant_trait_to_character(
        self,
        *,
        company: "Company",
        character: Character,
        user: "User",
        trait_id: UUID,
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

        Returns:
            The character trait that was added.

        Raises:
            PermissionDeniedError: If the user does not have permissions to add the trait.
            ValidationError: If the trait cannot be added.
        """
        trait = await Trait.filter(id=trait_id, is_archived=False).first()
        if trait is None:
            msg = "Trait not found"
            raise ValidationError(detail=msg)

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
            await self._guard_has_minimum_renown(trait, character)

        # Check if the trait already exists on the character
        existing = await CharacterTrait.filter(
            character_id=character.id,
            trait_id=trait_id,
        ).first()
        if existing:
            raise ConflictError(
                detail=f"Trait named '{trait.name}' already exists on character. Use modify trait value instead."
            )

        if currency != TraitModifyCurrency.NO_COST:
            await self._guard_can_afford_new_trait(trait, character, value, currency)

        character_trait = await CharacterTrait.create(
            character=character,
            trait=trait,
            value=0,
        )
        # Refetch with prefetched relations
        character_trait = await self._refetch_character_trait(character_trait.id)
        num_dots = value

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
        company: "Company",
        character: Character,
        user: "User",
        items: list[CharacterTraitAddConstant],
    ) -> BulkAssignTraitResponse:
        """Assign multiple constant traits to a character with best-effort semantics.

        Batch-fetch all trait documents and existing character traits up front for
        efficiency. Process each item individually with per-item transactions.

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
        await self._guard_permissions_free_trait_changes(company, character, user)

        # Batch-fetch all Trait documents
        trait_ids = [item.trait_id for item in items]
        all_traits = await Trait.filter(id__in=trait_ids, is_archived=False)
        trait_lookup: dict[UUID, Trait] = {t.id: t for t in all_traits}

        # Batch-fetch existing CharacterTraits for conflict detection
        existing_cts = await CharacterTrait.filter(
            character_id=character.id,
        ).select_related("trait")
        existing_trait_ids: set[UUID] = {
            ct.trait_id  # type: ignore[attr-defined]
            for ct in existing_cts
        }

        # Initialize running balances
        user_svc = UserXPService()
        campaign_xp = await user_svc.get_or_create_campaign_experience(
            character.user_player_id,  # type: ignore[attr-defined]
            character.campaign_id,  # type: ignore[attr-defined]
        )
        running_xp = campaign_xp.xp_current
        running_starting_points = character.starting_points

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
                    await self._guard_has_minimum_renown(trait, character)
                except ValidationError as exc:
                    failed.append(BulkAssignTraitFailure(trait_id=trait_id, error=exc.detail))
                    continue

            try:
                async with in_transaction():
                    # Create the CharacterTrait with value=0
                    character_trait = await CharacterTrait.create(
                        character=character,
                        trait=trait,
                        value=0,
                    )
                    # Refetch with prefetched relations
                    character_trait = await self._refetch_character_trait(character_trait.id)
                    num_dots = value

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
                        self._guard_is_safe_increase(character_trait, num_dots)
                        cost = await self._calculate_upgrade_cost(
                            character_trait,
                            num_dots,
                            character_id=character_trait.character_id,  # type: ignore[attr-defined]
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
                        )

                        # Adjust running balance only after successful apply
                        if is_flaw:
                            running_xp += cost
                        else:
                            running_xp -= cost

                    elif currency == TraitModifyCurrency.STARTING_POINTS:
                        # Pre-check running starting points balance
                        self._guard_is_safe_increase(character_trait, num_dots)
                        cost = await self._calculate_upgrade_cost(
                            character_trait,
                            num_dots,
                            character_id=character_trait.character_id,  # type: ignore[attr-defined]
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
                        )

                        # Adjust running balance only after successful apply
                        if is_flaw:
                            running_starting_points += cost
                        else:
                            running_starting_points -= cost
                    else:
                        assert_never(currency)

                    # Refetch for response serialization
                    result_ct = await self._refetch_character_trait(result_ct.id)
                    succeeded.append(
                        BulkAssignTraitSuccess(
                            trait_id=trait_id,
                            character_trait=CharacterTraitResponse.from_model(result_ct),
                        )
                    )
                    # Track the newly added trait to prevent duplicates within the batch
                    existing_trait_ids.add(trait_id)

            except (ValidationError, ConflictError, PermissionDeniedError, NotEnoughXPError) as e:
                failed.append(BulkAssignTraitFailure(trait_id=trait_id, error=str(e)))

        return BulkAssignTraitResponse(succeeded=succeeded, failed=failed)

    async def create_custom_trait(
        self,
        *,
        company: "Company",
        character: Character,
        user: "User",
        data: CharacterTraitCreateCustom,
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
        await self._guard_permissions_free_trait_changes(company, character, user)

        normalized_name = data.name.strip().title()

        existing = await CharacterTrait.filter(
            character_id=character.id,
            trait__name=normalized_name,
        ).first()
        if existing:
            raise ConflictError(detail=f"Trait named '{data.name}' already exists on character")

        existing_trait = await Trait.filter(
            name=normalized_name,
            is_custom=False,
            is_archived=False,
        ).first()
        if existing_trait:
            raise ConflictError(
                detail=f"Trait named '{data.name}' already exists. Custom traits must have a unique name."
            )

        parent_category = (
            await TraitCategory.filter(
                id=data.category_id,
                is_archived=False,
            )
            .select_related("sheet_section")
            .first()
        )
        if parent_category is None:
            msg = "Trait category not found"
            raise ValidationError(detail=msg)

        initial_cost = (
            data.initial_cost if data.initial_cost is not None else parent_category.initial_cost
        )
        upgrade_cost = (
            data.upgrade_cost if data.upgrade_cost is not None else parent_category.upgrade_cost
        )

        custom_trait = await Trait.create(
            name=normalized_name,
            description=data.description,
            max_value=data.max_value,
            min_value=data.min_value,
            show_when_zero=data.show_when_zero,
            initial_cost=initial_cost,
            upgrade_cost=upgrade_cost,
            custom_for_character_id=character.id,
            category=parent_category,
            sheet_section=parent_category.sheet_section,
            is_custom=True,
        )

        character_trait = await CharacterTrait.create(
            character=character,
            trait=custom_trait,
            value=data.value if data.value is not None else data.min_value,
        )

        # Refetch with prefetched relations
        character_trait = await self._refetch_character_trait(character_trait.id)
        await self.after_save(character_trait, character)
        return character_trait

    async def increase_character_trait_value(
        self,
        *,
        company: "Company",
        character: Character,
        user: "User",
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
        await self._guard_permissions_free_trait_changes(company, character, user)
        self._guard_is_safe_increase(character_trait, num_dots)

        character_trait.value += num_dots
        await character_trait.save(update_fields=["value", "date_modified"])
        await self.after_save(character_trait, character)
        return character_trait

    async def decrease_character_trait_value(
        self,
        *,
        company: "Company",
        character: Character,
        user: "User",
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
        await self._guard_permissions_free_trait_changes(company, character, user)
        self._guard_is_safe_decrease(character_trait, num_dots)

        character_trait.value -= num_dots
        await character_trait.save(update_fields=["value", "date_modified"])
        await self.after_save(character_trait, character)
        return character_trait

    async def _apply_xp_change(
        self,
        *,
        character: Character,
        user: "User",
        character_trait: CharacterTrait,
        num_dots: int,
        is_increase: bool,
        deleting_trait: bool = False,
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

        Returns:
            The updated CharacterTrait.
        """
        self.guard_user_can_manage_character(character, user)

        cost: int
        if is_increase:
            self._guard_is_safe_increase(character_trait, num_dots)
            cost = await self._calculate_upgrade_cost(
                character_trait,
                num_dots,
                character_id=character_trait.character_id,  # type: ignore[attr-defined]
            )
        else:
            if not deleting_trait:
                self._guard_is_safe_decrease(character_trait, num_dots)
            cost = await self._calculate_downgrade_savings(
                character_trait,
                num_dots,
                character_id=character_trait.character_id,  # type: ignore[attr-defined]
            )

        user_svc = UserXPService()
        user_player_id = character.user_player_id  # type: ignore[attr-defined]
        campaign_id = character.campaign_id  # type: ignore[attr-defined]
        is_flaw = await self._is_flaw_trait(character_trait)

        # Flaw traits invert the currency direction
        if is_increase == is_flaw:
            await user_svc.add_xp(user_player_id, campaign_id, cost, update_total=False)
        else:
            await user_svc.spend_xp(user_player_id, campaign_id, cost)

        character_trait.value += num_dots if is_increase else -num_dots
        await character_trait.save(update_fields=["value", "date_modified"])
        await self.after_save(character_trait, character)
        return character_trait

    async def _apply_starting_points_change(
        self,
        *,
        user: "User",
        character: Character,
        character_trait: CharacterTrait,
        num_dots: int,
        is_increase: bool,
        deleting_trait: bool = False,
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

        Returns:
            The updated CharacterTrait.
        """
        self.guard_user_can_manage_character(character, user)

        cost: int
        if is_increase:
            self._guard_is_safe_increase(character_trait, num_dots)
            cost = await self._calculate_upgrade_cost(
                character_trait,
                num_dots,
                character_id=character_trait.character_id,  # type: ignore[attr-defined]
            )
        else:
            if not deleting_trait:
                self._guard_is_safe_decrease(character_trait, num_dots)
            cost = await self._calculate_downgrade_savings(
                character_trait,
                num_dots,
                character_id=character_trait.character_id,  # type: ignore[attr-defined]
            )

        is_flaw = await self._is_flaw_trait(character_trait)

        # Flaw traits invert the currency direction
        if is_increase == is_flaw:
            character.starting_points += cost
        else:
            if character.starting_points < cost:
                raise ValidationError(detail="Not enough starting points")
            character.starting_points -= cost
        await character.save(update_fields=["starting_points", "date_modified"])

        character_trait.value += num_dots if is_increase else -num_dots
        await character_trait.save(update_fields=["value", "date_modified"])
        await self.after_save(character_trait, character)
        return character_trait

    async def list_character_traits(
        self,
        character: Character,
        limit: int = 10,
        offset: int = 0,
        *,
        category_id: UUID | None = None,
        is_rollable: bool | None = None,
    ) -> tuple[int, list[CharacterTrait]]:
        """List all character traits.

        Args:
            character: The character to list the traits for.
            limit: The limit of traits to return.
            offset: The offset of the traits to return.
            category_id: The category id to filter the traits by.
            is_rollable: Whether to filter the traits by rollable traits.

        Returns:
            A tuple containing the total number of traits and the list of traits.
        """
        filters: dict[str, object] = {"character_id": character.id}
        if is_rollable is not None:
            filters["trait__is_rollable"] = is_rollable
        if category_id is not None:
            filters["trait__category_id"] = category_id

        queryset = CharacterTrait.filter(**filters)

        count, traits = await asyncio.gather(
            queryset.count(),
            queryset.prefetch_related(*CHARACTER_TRAIT_PREFETCH)
            .order_by("trait__category_id")
            .offset(offset)
            .limit(limit),
        )
        return count, list(traits)

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
            A TraitValueOptionsResponse containing current value, min/max bounds,
            current XP and starting points, and options for each possible target value.
        """
        user_svc = UserXPService()
        user_player_id = character.user_player_id  # type: ignore[attr-defined]
        campaign_id = character.campaign_id  # type: ignore[attr-defined]
        campaign_experience = await user_svc.get_or_create_campaign_experience(
            user_player_id, campaign_id
        )

        current_value = character_trait.value
        xp_current = campaign_experience.xp_current
        starting_points_current = character.starting_points

        is_flaw, upgrade_costs, downgrade_savings = await asyncio.gather(
            self._is_flaw_trait(character_trait),
            self.calculate_all_upgrade_costs(character_trait),
            self.calculate_all_downgrade_savings(character_trait),
        )

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
            name=character_trait.trait.name,
            current_value=current_value,
            trait=TraitResponse.from_model(character_trait.trait),
            xp_current=xp_current,
            starting_points_current=starting_points_current,
            options=options,
        )

    async def modify_trait_value(  # noqa: PLR0911, PLR0913
        self,
        *,
        company: "Company",
        user: "User",
        character: Character,
        character_trait: CharacterTrait,
        target_value: int,
        currency: TraitModifyCurrency,
        deleting_trait: bool = False,
        recoup_store: Store | None = None,
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
            recoup_store: Optional Redis store used to enforce permission_recoup_xp.
                When None, the gate is skipped (callers without request context).

        Returns:
            The updated CharacterTrait.

        Raises:
            ValidationError: If the target value is invalid or unaffordable.
            PermissionDeniedError: If the user lacks required permissions, including
                recoup-XP enforcement.
        """
        current_value = character_trait.value
        num_dots = abs(target_value - current_value)

        if num_dots == 0:
            return character_trait

        is_increase = target_value > current_value

        # XP-currency recoup gate. NO_COST and STARTING_POINTS bypass entirely.
        if currency == TraitModifyCurrency.XP and recoup_store is not None:
            await self._enforce_recoup_xp_permission(
                company=company,
                user=user,
                character=character,
                character_trait=character_trait,
                current_value=current_value,
                target_value=target_value,
                is_increase=is_increase,
                store=recoup_store,
            )

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
                )
            return await self._apply_starting_points_change(
                user=user,
                character=character,
                character_trait=character_trait,
                num_dots=num_dots,
                is_increase=True,
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
            )
        return await self._apply_starting_points_change(
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=num_dots,
            is_increase=False,
            deleting_trait=deleting_trait,
        )

    async def delete_trait(
        self,
        *,
        company: "Company",
        user: "User",
        character: Character,
        character_trait: CharacterTrait,
        currency: TraitModifyCurrency | None = None,
        recoup_store: Store | None = None,
    ) -> None:
        """Delete a trait from a character.

        Args:
            company: The company.
            user: The user deleting the trait.
            character: The character to delete the trait from.
            character_trait: The trait to delete.
            currency: The currency to use to recoup the cost of the trait.
            recoup_store: Optional Redis store used to enforce permission_recoup_xp.
                When None, the gate is skipped (callers without request context).

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
                recoup_store=recoup_store,
            )

        if character_trait.trait.is_custom:
            await character_trait.trait.delete()
        await character_trait.delete()
