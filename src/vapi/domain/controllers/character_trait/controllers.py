"""Character trait controllers."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, post, put
from litestar.params import Parameter

from vapi.db.models import Character, CharacterTrait, Company, User  # noqa: TC001
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CharacterTraitService
from vapi.lib.guards import (
    developer_company_user_guard,
    user_character_player_or_storyteller_guard,
    user_storyteller_guard,
)
from vapi.openapi.tags import APITags

from . import docs, dto


class CharacterTraitController(Controller):
    """Character trait controller."""

    tags = [APITags.CHARACTERS_TRAITS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id),
        "character": Provide(deps.provide_character_by_id_and_company),
        "character_trait": Provide(deps.provide_character_trait_by_id),
    }
    guards = [developer_company_user_guard]

    @get(
        path=urls.Characters.TRAITS,
        summary="List character traits",
        operation_id="listCharacterTraits",
        description=docs.LIST_CHARACTER_TRAITS_DESCRIPTION,
        cache=True,
    )
    async def list_character_traits(
        self,
        character: Character,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        parent_category_id: Annotated[
            PydanticObjectId, Parameter(description="Show traits in this parent category.")
        ]
        | None = None,
    ) -> OffsetPagination[CharacterTrait]:
        """List all character traits."""
        service = CharacterTraitService()
        count, traits = await service.list_character_traits(
            character=character,
            limit=limit,
            offset=offset,
            parent_category_id=parent_category_id,
        )
        return OffsetPagination(items=traits, limit=limit, offset=offset, total=count)

    @get(
        path=urls.Characters.TRAIT_DETAIL,
        summary="Get character trait",
        operation_id="getCharacterTrait",
        description=docs.GET_CHARACTER_TRAIT_DESCRIPTION,
        cache=True,
    )
    async def get_character_trait(self, character_trait: CharacterTrait) -> CharacterTrait:
        """Get a character trait by Character Trait ID or Trait ID."""
        return character_trait

    @post(
        path=urls.Characters.TRAIT_ASSIGN,
        summary="Assign trait to character",
        operation_id="assignTraitToCharacter",
        description=docs.ASSIGN_TRAIT_DESCRIPTION,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def assign_trait_to_character(
        self,
        company: Company,
        user: User,
        character: Character,
        data: dto.CharacterTraitAddConstant,
    ) -> CharacterTrait:
        """Add a trait to a character."""
        service = CharacterTraitService()
        return await service.add_constant_trait_to_character(
            company=company,
            user=user,
            character=character,
            trait_id=data.trait_id,
            value=data.value,
        )

    @post(
        path=urls.Characters.TRAIT_CREATE,
        summary="Create custom trait",
        operation_id="createCustomTrait",
        description=docs.CREATE_CUSTOM_TRAIT_DESCRIPTION,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def create_custom_trait(
        self,
        company: Company,
        user: User,
        character: Character,
        data: dto.CharacterTraitCreateCustomDTO,
    ) -> CharacterTrait:
        """Create a custom trait."""
        service = CharacterTraitService()
        return await service.create_custom_trait(
            company=company,
            user=user,
            character=character,
            data=data,
        )

    @put(
        path=urls.Characters.TRAIT_INCREASE,
        summary="Increase trait value",
        operation_id="increaseCharacterTraitValue",
        description=docs.INCREASE_TRAIT_VALUE_DESCRIPTION,
        guards=[user_storyteller_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def increase_character_trait_value(
        self,
        company: Company,
        user: User,
        character: Character,
        character_trait: CharacterTrait,
        data: dto.TraitValueDTO,
    ) -> CharacterTrait:
        """Increase a character trait value."""
        service = CharacterTraitService()
        return await service.increase_character_trait_value(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=data.num_dots,
        )

    @put(
        path=urls.Characters.TRAIT_DECREASE,
        summary="Decrease trait value",
        operation_id="decreaseCharacterTraitValue",
        description=docs.DECREASE_TRAIT_VALUE_DESCRIPTION,
        guards=[user_storyteller_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def decrease_character_trait_value(
        self,
        company: Company,
        user: User,
        character: Character,
        character_trait: CharacterTrait,
        data: dto.TraitValueDTO,
    ) -> CharacterTrait:
        """Decrease a character trait value."""
        service = CharacterTraitService()
        return await service.decrease_character_trait_value(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=data.num_dots,
        )

    @put(
        path=urls.Characters.TRAIT_XP_PURCHASE,
        summary="Increase trait value with xp",
        operation_id="purchaseCharacterTraitXp",
        description=docs.PURCHASE_TRAIT_XP_DESCRIPTION,
        tags=[APITags.EXPERIENCE.name],
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def purchase_character_trait_xp(
        self,
        user: User,
        character: Character,
        character_trait: CharacterTrait,
        data: dto.TraitValueDTO,
    ) -> CharacterTrait:
        """Purchase a character trait value with xp."""
        service = CharacterTraitService()
        return await service.purchase_trait_value_with_xp(
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=data.num_dots,
        )

    @put(
        path=urls.Characters.TRAIT_XP_REFUND,
        summary="Decrease trait value with xp",
        operation_id="refundCharacterTraitXp",
        description=docs.REFUND_TRAIT_XP_DESCRIPTION,
        tags=[APITags.EXPERIENCE.name],
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def refund_character_trait_xp(
        self,
        user: User,
        character: Character,
        character_trait: CharacterTrait,
        data: dto.TraitValueDTO,
    ) -> CharacterTrait:
        """Decrease a character trait value."""
        service = CharacterTraitService()
        return await service.refund_trait_value_with_xp(
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=data.num_dots,
        )

    @put(
        path=urls.Characters.TRAIT_STARTINGPOINTS_PURCHASE,
        summary="Purchase starting points",
        operation_id="purchaseCharacterTraitStartingPoints",
        description=docs.PURCHASE_STARTING_POINTS_DESCRIPTION,
        tags=[APITags.EXPERIENCE.name],
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def purchase_character_trait_starting_points(
        self,
        user: User,
        character: Character,
        character_trait: CharacterTrait,
        data: dto.TraitValueDTO,
    ) -> CharacterTrait:
        """Purchase starting points."""
        service = CharacterTraitService()
        return await service.purchase_trait_increase_with_starting_points(
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=data.num_dots,
        )

    @put(
        path=urls.Characters.TRAIT_STARTINGPOINTS_REFUND,
        summary="Refund starting points",
        operation_id="refundCharacterTraitStartingPoints",
        description=docs.REFUND_STARTING_POINTS_DESCRIPTION,
        tags=[APITags.EXPERIENCE.name],
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def refund_character_trait_starting_points(
        self,
        user: User,
        character: Character,
        character_trait: CharacterTrait,
        data: dto.TraitValueDTO,
    ) -> CharacterTrait:
        """Refund starting points."""
        service = CharacterTraitService()
        return await service.refund_trait_decrease_with_starting_points(
            user=user,
            character=character,
            character_trait=character_trait,
            num_dots=data.num_dots,
        )

    @delete(
        path=urls.Characters.TRAIT_DELETE,
        summary="Remove trait from character",
        operation_id="deleteCharacterTrait",
        description=docs.DELETE_CHARACTER_TRAIT_DESCRIPTION,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def delete_character_trait(
        self,
        user: User,
        character: Character,
        character_trait: CharacterTrait,
    ) -> None:
        """Delete a character trait."""
        service = CharacterTraitService()
        service.guard_user_can_manage_character(character=character, user=user)
        if character_trait.trait.is_custom:  # type: ignore [attr-defined]
            await character_trait.trait.delete()  # type: ignore [attr-defined]

        await character_trait.delete()
