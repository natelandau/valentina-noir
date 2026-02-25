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
from vapi.lib.guards import developer_company_user_guard
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
        after_response=hooks.post_data_update_hook,
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
        after_response=hooks.post_data_update_hook,
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

    @get(
        path=urls.Characters.TRAIT_VALUE_OPTIONS,
        summary="Get trait value options",
        operation_id="getTraitValueOptions",
        description=docs.GET_VALUE_OPTIONS_DESCRIPTION,
        tags=[APITags.EXPERIENCE.name],
    )
    async def get_value_options(
        self,
        character: Character,
        character_trait: CharacterTrait,
    ) -> dto.TraitValueOptionsResponse:
        """Get all possible target values with costs and affordability."""
        service = CharacterTraitService()
        return await service.get_value_options(
            character=character,
            character_trait=character_trait,
        )

    @put(
        path=urls.Characters.TRAIT_VALUE,
        summary="Modify trait value",
        operation_id="modifyTraitValue",
        description=docs.MODIFY_VALUE_DESCRIPTION,
        tags=[APITags.EXPERIENCE.name],
        after_response=hooks.post_data_update_hook,
    )
    async def modify_value(
        self,
        company: Company,
        user: User,
        character: Character,
        character_trait: CharacterTrait,
        data: dto.TraitModifyRequest,
    ) -> CharacterTrait:
        """Modify a character trait to a target value."""
        service = CharacterTraitService()
        return await service.modify_trait_value(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            target_value=data.target_value,
            currency=data.currency,
        )

    @delete(
        path=urls.Characters.TRAIT_DELETE,
        summary="Remove trait from character",
        operation_id="deleteCharacterTrait",
        description=docs.DELETE_CHARACTER_TRAIT_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
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
