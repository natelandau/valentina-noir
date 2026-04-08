"""Character trait controllers."""

from typing import Annotated
from uuid import UUID

from litestar import Request
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, post, put
from litestar.params import Parameter

from vapi.config import settings
from vapi.constants import MAX_BULK_TRAIT_ASSIGN, TraitModifyCurrency
from vapi.db.sql_models.character import Character, CharacterTrait
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CharacterTraitService
from vapi.lib.exceptions import ValidationError
from vapi.lib.guards import developer_company_user_guard, user_active_guard
from vapi.openapi.tags import APITags

from . import docs
from .dto import (
    BulkAssignTraitResponse,
    CharacterTraitAddConstant,
    CharacterTraitCreateCustom,
    CharacterTraitResponse,
    TraitModifyRequest,
    TraitValueOptionsResponse,
)


class CharacterTraitController(Controller):
    """Character trait controller."""

    tags = [APITags.CHARACTERS_TRAITS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "character": Provide(deps.provide_character_by_id_and_company),
        "character_trait": Provide(deps.provide_character_trait_by_id),
        "developer": Provide(deps.provide_developer_from_request),
    }
    guards = [developer_company_user_guard, user_active_guard]

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
        category_id: Annotated[UUID, Parameter(description="Filter by trait category.")]
        | None = None,
        is_rollable: Annotated[bool | None, Parameter(description="Show rollable traits.")] = None,
    ) -> OffsetPagination[CharacterTraitResponse]:
        """List all character traits."""
        service = CharacterTraitService()
        count, traits = await service.list_character_traits(
            character=character,
            limit=limit,
            offset=offset,
            category_id=category_id,
            is_rollable=is_rollable,
        )
        return OffsetPagination(
            items=[CharacterTraitResponse.from_model(t) for t in traits],
            limit=limit,
            offset=offset,
            total=count,
        )

    @get(
        path=urls.Characters.TRAIT_DETAIL,
        summary="Get character trait",
        operation_id="getCharacterTrait",
        description=docs.GET_CHARACTER_TRAIT_DESCRIPTION,
        cache=True,
    )
    async def get_character_trait(self, character_trait: CharacterTrait) -> CharacterTraitResponse:
        """Get a character trait by Character Trait ID or Trait ID."""
        return CharacterTraitResponse.from_model(character_trait)

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
        data: CharacterTraitAddConstant,
    ) -> CharacterTraitResponse:
        """Add a trait to a character."""
        service = CharacterTraitService()
        ct = await service.add_constant_trait_to_character(
            company=company,
            user=user,
            character=character,
            trait_id=data.trait_id,
            value=data.value,
            currency=data.currency,
        )
        return CharacterTraitResponse.from_model(ct)

    @post(
        path=urls.Characters.TRAIT_BULK_ASSIGN,
        summary="Bulk assign traits to character",
        operation_id="bulkAssignTraitsToCharacter",
        description=docs.BULK_ASSIGN_TRAITS_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
        status_code=200,
    )
    async def bulk_assign_traits_to_character(
        self,
        company: Company,
        user: User,
        character: Character,
        data: list[CharacterTraitAddConstant],
    ) -> BulkAssignTraitResponse:
        """Assign multiple traits to a character in a single request."""
        if len(data) > MAX_BULK_TRAIT_ASSIGN:
            msg = f"Batch size must not exceed {MAX_BULK_TRAIT_ASSIGN} items"
            raise ValidationError(detail=msg)

        service = CharacterTraitService()
        return await service.bulk_add_constant_traits_to_character(
            company=company,
            user=user,
            character=character,
            items=data,
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
        data: CharacterTraitCreateCustom,
    ) -> CharacterTraitResponse:
        """Create a custom trait."""
        service = CharacterTraitService()
        ct = await service.create_custom_trait(
            company=company,
            user=user,
            character=character,
            data=data,
        )
        return CharacterTraitResponse.from_model(ct)

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
    ) -> TraitValueOptionsResponse:
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
        request: Request,
        company: Company,
        user: User,
        character: Character,
        character_trait: CharacterTrait,
        data: TraitModifyRequest,
    ) -> CharacterTraitResponse:
        """Modify a character trait to a target value."""
        service = CharacterTraitService()
        recoup_store = request.app.stores.get(settings.stores.recoup_session_key)
        ct = await service.modify_trait_value(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            target_value=data.target_value,
            currency=data.currency,
            recoup_store=recoup_store,
        )
        return CharacterTraitResponse.from_model(ct)

    @delete(
        path=urls.Characters.TRAIT_DELETE,
        summary="Remove trait from character",
        operation_id="deleteCharacterTrait",
        description=docs.DELETE_CHARACTER_TRAIT_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def delete_character_trait(
        self,
        request: Request,
        company: Company,
        user: User,
        character: Character,
        character_trait: CharacterTrait,
        currency: Annotated[
            TraitModifyCurrency | None,
            Parameter(description="The currency to use to recoup the cost of the trait. Optional."),
        ] = None,
    ) -> None:
        """Delete a character trait."""
        service = CharacterTraitService()
        service.guard_user_can_manage_character(character=character, user=user)
        recoup_store = request.app.stores.get(settings.stores.recoup_session_key)
        await service.delete_trait(
            company=company,
            user=user,
            character=character,
            character_trait=character_trait,
            currency=currency,
            recoup_store=recoup_store,
        )
