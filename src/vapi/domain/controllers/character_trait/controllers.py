"""Character trait controllers."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, post, put
from litestar.params import Parameter

from vapi.db.models import Character, CharacterTrait  # noqa: TC001
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CharacterTraitService
from vapi.lib.guards import (
    developer_company_user_guard,
    user_character_player_or_storyteller_guard,
    user_storyteller_guard,
)
from vapi.openapi.tags import APITags

from . import dto  # noqa: TC001

# TODO: Add guards for player ownership or storyteller for patches and deletions.


class CharacterTraitController(Controller):
    """Character trait controller."""

    tags = [APITags.CHARACTERS_TRAITS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "character": Provide(deps.provide_character_by_id_and_company),
        "character_trait": Provide(deps.provide_character_trait_by_id),
        "user": Provide(deps.provide_user_by_id),
    }
    guards = [developer_company_user_guard]

    @get(
        path=urls.Characters.TRAITS,
        summary="List character traits",
        operation_id="listCharacterTraits",
        description="Retrieve a paginated list of traits assigned to a character. Each trait includes the base trait definition and the character's current value.",
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
        description="Retrieve a specific character trait including the base trait definition and current value.",
        cache=True,
    )
    async def get_character_trait(self, character_trait: CharacterTrait) -> CharacterTrait:
        """Get a character trait by Character Trait ID or Trait ID."""
        return character_trait

    @post(
        path=urls.Characters.TRAIT_ASSIGN,
        summary="Assign trait to character",
        operation_id="assignTraitToCharacter",
        description="Assign an existing trait to a character with an initial value. The trait must not already exist on the character and the value must not exceed the trait's maximum.",
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def assign_trait_to_character(
        self,
        character: Character,
        data: dto.CharacterTraitAddConstant,
    ) -> CharacterTrait:
        """Add a trait to a character."""
        service = CharacterTraitService()
        return await service.add_constant_trait_to_character(character, data.trait_id, data.value)

    @post(
        path=urls.Characters.TRAIT_CREATE,
        summary="Create custom trait",
        operation_id="createCustomTrait",
        description="Create a new custom trait unique to this character. Specify the trait name, category, and optional cost configuration. Custom traits are useful for specializations or homebrew content.",
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def create_custom_trait(
        self,
        character: Character,
        data: dto.CharacterTraitCreateCustomDTO,
    ) -> CharacterTrait:
        """Create a custom trait."""
        service = CharacterTraitService()
        return await service.create_custom_trait(character, data)

    @put(
        path=urls.Characters.TRAIT_INCREASE,
        summary="Increase trait value",
        operation_id="increaseCharacterTraitValue",
        description="Increase a character trait's value. The value cannot exceed the trait's maximum.",
        guards=[user_storyteller_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def increase_character_trait_value(
        self,
        character_trait: CharacterTrait,
        data: dto.TraitValueDTO,
    ) -> CharacterTrait:
        """Increase a character trait value."""
        service = CharacterTraitService()
        return await service.increase_character_trait_value(character_trait, data.num_dots)

    @put(
        path=urls.Characters.TRAIT_DECREASE,
        summary="Decrease trait value",
        operation_id="decreaseCharacterTraitValue",
        description="Decrease a character trait's value. The value cannot go below zero.",
        guards=[user_storyteller_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def decrease_character_trait_value(
        self,
        character_trait: CharacterTrait,
        data: dto.TraitValueDTO,
    ) -> CharacterTrait:
        """Decrease a character trait value."""
        service = CharacterTraitService()
        return await service.decrease_character_trait_value(character_trait, data.num_dots)

    @put(
        path=urls.Characters.TRAIT_XP_PURCHASE,
        summary="Increase trait value with xp",
        operation_id="purchaseCharacterTraitXp",
        description="Purchase trait dots with experience points. The XP will be spent from the users' campaign experience points.",
        tags=[APITags.EXPERIENCE.name],
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def purchase_character_trait_xp(
        self,
        character_trait: CharacterTrait,
        character: Character,
        data: dto.TraitValueDTO,
    ) -> CharacterTrait:
        """Purchase a character trait value with xp."""
        service = CharacterTraitService()
        return await service.purchase_trait_value_with_xp(
            character=character,
            character_trait=character_trait,
            num_dots=data.num_dots,
        )

    @put(
        path=urls.Characters.TRAIT_XP_REFUND,
        summary="Decrease trait value with xp",
        operation_id="refundCharacterTraitXp",
        description="Refund trait dots with experience points. By downgrading the number of dots on the trait, the user will be refunded the experience points spent on the trait dots. The XP will be added to the user's campaign experience points.",
        tags=[APITags.EXPERIENCE.name],
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def refund_character_trait_xp(
        self,
        character_trait: CharacterTrait,
        character: Character,
        data: dto.TraitValueDTO,
    ) -> CharacterTrait:
        """Decrease a character trait value."""
        service = CharacterTraitService()
        return await service.refund_trait_value_with_xp(
            character=character,
            character_trait=character_trait,
            num_dots=data.num_dots,
        )

    @put(
        path=urls.Characters.TRAIT_STARTINGPOINTS_PURCHASE,
        summary="Purchase starting points",
        operation_id="purchaseCharacterTraitStartingPoints",
        description="Purchase starting points with experience points. The XP will be spent from the users' campaign experience points.",
        tags=[APITags.EXPERIENCE.name],
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def purchase_character_trait_starting_points(
        self,
        character_trait: CharacterTrait,
        character: Character,
        data: dto.TraitValueDTO,
    ) -> CharacterTrait:
        """Purchase starting points."""
        service = CharacterTraitService()
        return await service.purchase_trait_increase_with_starting_points(
            character=character,
            character_trait=character_trait,
            num_dots=data.num_dots,
        )

    @put(
        path=urls.Characters.TRAIT_STARTINGPOINTS_REFUND,
        summary="Refund starting points",
        operation_id="refundCharacterTraitStartingPoints",
        description="Refund starting points with experience points. The XP will be added to the user's campaign experience points.",
        tags=[APITags.EXPERIENCE.name],
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def refund_character_trait_starting_points(
        self,
        character: Character,
        character_trait: CharacterTrait,
        data: dto.TraitValueDTO,
    ) -> CharacterTrait:
        """Refund starting points."""
        service = CharacterTraitService()
        return await service.refund_trait_decrease_with_starting_points(
            character=character,
            character_trait=character_trait,
            num_dots=data.num_dots,
        )

    @delete(
        path=urls.Characters.TRAIT_DELETE,
        summary="Remove trait from character",
        operation_id="deleteCharacterTrait",
        description="Remove a trait from a character. If the trait is custom, it will also be deleted. This action cannot be undone.",
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def delete_character_trait(
        self,
        character_trait: CharacterTrait,
    ) -> None:
        """Delete a character trait."""
        if character_trait.trait.is_custom:  # type: ignore [attr-defined]
            await character_trait.trait.delete()  # type: ignore [attr-defined]

        await character_trait.delete()
