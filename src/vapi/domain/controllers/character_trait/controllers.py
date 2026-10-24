"""Character trait controllers."""

from typing import Annotated
from uuid import UUID

from litestar import Request
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post, put
from litestar.params import Parameter

from vapi.config import settings
from vapi.constants import MAX_BULK_TRAIT_ASSIGN, AuditOperation, TraitModifyCurrency
from vapi.db.sql_models.character import Character, CharacterTrait, CharacterTraitSpecialty
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CharacterTraitService, TrackerService
from vapi.lib.exceptions import NotFoundError, ValidationError
from vapi.lib.guards import (
    developer_company_user_guard,
    storyteller_character_access_guard,
    user_active_guard,
    user_character_player_or_storyteller_guard,
)
from vapi.openapi.tags import APITags

from . import docs
from .dto import (
    BulkAssignTraitResponse,
    CharacterTraitAddConstant,
    CharacterTraitCreateCustom,
    CharacterTraitResponse,
    CharacterTraitSpecialtyCreate,
    CharacterTraitSpecialtyUpdate,
    TrackerActionRequest,
    TrackerResponse,
    TrackerStateSet,
    TraitModifyRequest,
    TraitValueOptionsResponse,
    build_tracker_response,
)


class CharacterTraitController(Controller):
    """Character trait controller."""

    tags = [APITags.CHARACTERS_TRAITS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "acting_user": Provide(deps.provide_acting_user),
        "character": Provide(deps.provide_character_by_id_and_company),
        "character_trait": Provide(deps.provide_character_trait_by_id),
        "specialty": Provide(deps.provide_character_trait_specialty_by_id),
        "developer": Provide(deps.provide_developer_from_request),
    }
    guards = [developer_company_user_guard, user_active_guard, storyteller_character_access_guard]

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
            items=[
                CharacterTraitResponse.from_model(t, game_version=character.game_version)
                for t in traits
            ],
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
    async def get_character_trait(
        self, character: Character, character_trait: CharacterTrait
    ) -> CharacterTraitResponse:
        """Get a character trait by Character Trait ID or Trait ID."""
        return CharacterTraitResponse.from_model(
            character_trait, game_version=character.game_version
        )

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
        acting_user: User,
        character: Character,
        data: CharacterTraitAddConstant,
        request: Request,
    ) -> CharacterTraitResponse:
        """Add a trait to a character."""
        service = CharacterTraitService()
        ct = await service.add_constant_trait_to_character(
            company=company,
            user=acting_user,
            character=character,
            trait_id=data.trait_id,
            value=data.value,
            currency=data.currency,
        )
        request.state.audit_description = f"Assign trait '{ct.trait.name}' at value {ct.value} to character '{character.name_first} {character.name_last}'"
        return CharacterTraitResponse.from_model(ct, game_version=character.game_version)

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
        acting_user: User,
        character: Character,
        data: list[CharacterTraitAddConstant],
        request: Request,
    ) -> BulkAssignTraitResponse:
        """Assign multiple traits to a character in a single request."""
        if len(data) > MAX_BULK_TRAIT_ASSIGN:
            msg = f"Batch size must not exceed {MAX_BULK_TRAIT_ASSIGN} items"
            raise ValidationError(detail=msg)

        service = CharacterTraitService()
        request.state.audit_description = f"Bulk assign {len(data)} traits to character '{character.name_first} {character.name_last}'"
        return await service.bulk_add_constant_traits_to_character(
            company=company,
            user=acting_user,
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
        acting_user: User,
        character: Character,
        data: CharacterTraitCreateCustom,
        request: Request,
    ) -> CharacterTraitResponse:
        """Create a custom trait."""
        service = CharacterTraitService()
        ct = await service.create_custom_trait(
            company=company,
            user=acting_user,
            character=character,
            data=data,
        )
        request.state.audit_description = f"Create custom trait '{ct.trait.name}' at value {ct.value} for character '{character.name_first} {character.name_last}'"
        return CharacterTraitResponse.from_model(ct, game_version=character.game_version)

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
        acting_user: User,
        character: Character,
        character_trait: CharacterTrait,
        data: TraitModifyRequest,
    ) -> CharacterTraitResponse:
        """Modify a character trait to a target value."""
        service = CharacterTraitService()
        recoup_store = request.app.stores.get(settings.stores.recoup_session_key)
        ct = await service.modify_trait_value(
            company=company,
            user=acting_user,
            character=character,
            character_trait=character_trait,
            target_value=data.target_value,
            currency=data.currency,
            recoup_store=recoup_store,
        )
        request.state.audit_description = f"Modify trait '{ct.trait.name}' to {ct.value} for character '{character.name_first} {character.name_last}'"
        if service.removed_specialty_names:
            request.state.audit_changes = {
                "specialties": {"old": service.removed_specialty_names, "new": []}
            }
        return CharacterTraitResponse.from_model(ct, game_version=character.game_version)

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
        acting_user: User,
        character: Character,
        character_trait: CharacterTrait,
        currency: Annotated[
            TraitModifyCurrency | None,
            Parameter(description="The currency to use to recoup the cost of the trait. Optional."),
        ] = None,
    ) -> None:
        """Delete a character trait."""
        service = CharacterTraitService()
        await service.guard_user_can_manage_character(character=character, user=acting_user)
        recoup_store = request.app.stores.get(settings.stores.recoup_session_key)
        request.state.audit_description = f"Delete trait '{character_trait.trait.name}' from character '{character.name_first} {character.name_last}'"
        await service.delete_trait(
            company=company,
            user=acting_user,
            character=character,
            character_trait=character_trait,
            currency=currency,
            recoup_store=recoup_store,
        )
        if service.removed_specialty_names:
            request.state.audit_changes = {
                "specialties": {"old": service.removed_specialty_names, "new": []}
            }

    @post(
        path=urls.Characters.TRAIT_SPECIALTIES,
        summary="Add trait specialty",
        operation_id="addCharacterTraitSpecialty",
        description=docs.ADD_SPECIALTY_DESCRIPTION,
        tags=[APITags.CHARACTERS_TRAITS.name, APITags.EXPERIENCE.name],
        after_response=hooks.post_data_update_hook,
        status_code=201,
    )
    async def add_specialty(
        self,
        request: Request,
        company: Company,
        acting_user: User,
        character: Character,
        character_trait: CharacterTrait,
        data: CharacterTraitSpecialtyCreate,
    ) -> CharacterTraitResponse:
        """Add a specialty to an ability trait."""
        service = CharacterTraitService()
        ct = await service.add_specialty(
            company=company,
            user=acting_user,
            character=character,
            character_trait=character_trait,
            name=data.name,
            currency=data.currency,
        )
        request.state.audit_description = f"Add specialty '{data.name.strip()}' to trait '{ct.trait.name}' for character '{character.name_first} {character.name_last}'"
        return CharacterTraitResponse.from_model(ct, game_version=character.game_version)

    @patch(
        path=urls.Characters.TRAIT_SPECIALTY_DETAIL,
        summary="Update trait specialty",
        operation_id="updateCharacterTraitSpecialty",
        description=docs.UPDATE_SPECIALTY_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def update_specialty(
        self,
        request: Request,
        acting_user: User,
        character: Character,
        character_trait: CharacterTrait,
        specialty: CharacterTraitSpecialty,
        data: CharacterTraitSpecialtyUpdate,
    ) -> CharacterTraitResponse:
        """Rename a specialty."""
        service = CharacterTraitService()
        old_name = specialty.name
        ct = await service.rename_specialty(
            user=acting_user,
            character=character,
            character_trait=character_trait,
            specialty=specialty,
            name=data.name,
        )
        request.state.audit_description = f"Rename specialty '{old_name}' to '{specialty.name}' on trait '{ct.trait.name}' for character '{character.name_first} {character.name_last}'"
        request.state.audit_changes = {"name": {"old": old_name, "new": specialty.name}}
        return CharacterTraitResponse.from_model(ct, game_version=character.game_version)

    @delete(
        path=urls.Characters.TRAIT_SPECIALTY_DETAIL,
        summary="Remove trait specialty",
        operation_id="deleteCharacterTraitSpecialty",
        description=docs.DELETE_SPECIALTY_DESCRIPTION,
        tags=[APITags.CHARACTERS_TRAITS.name, APITags.EXPERIENCE.name],
        after_response=hooks.post_data_update_hook,
    )
    async def delete_specialty(
        self,
        request: Request,
        company: Company,
        acting_user: User,
        character: Character,
        character_trait: CharacterTrait,
        specialty: CharacterTraitSpecialty,
    ) -> None:
        """Remove a specialty from an ability trait."""
        service = CharacterTraitService()
        request.state.audit_description = f"Remove specialty '{specialty.name}' from trait '{character_trait.trait.name}' for character '{character.name_first} {character.name_last}'"
        await service.remove_specialty(
            company=company,
            user=acting_user,
            character=character,
            specialty=specialty,
        )

    @get(
        path=urls.Characters.TRAIT_TRACKER,
        summary="Get trait tracker",
        operation_id="getTraitTracker",
        description=docs.GET_TRAIT_TRACKER_DESCRIPTION,
        cache=True,
    )
    async def get_trait_tracker(
        self, character: Character, character_trait: CharacterTrait
    ) -> TrackerResponse:
        """Get the in-play tracker state of a character trait."""
        tracker = build_tracker_response(character_trait, game_version=character.game_version)
        if tracker is None:
            raise NotFoundError(detail="Trait has no tracker")
        return tracker

    @put(
        path=urls.Characters.TRAIT_TRACKER,
        summary="Set trait tracker",
        operation_id="setTraitTracker",
        description=docs.SET_TRAIT_TRACKER_DESCRIPTION,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.post_data_update_hook,
        status_code=200,
    )
    async def set_trait_tracker(
        self,
        request: Request,
        character: Character,
        character_trait: CharacterTrait,
        acting_user: User,  # noqa: ARG002
        data: TrackerStateSet,
    ) -> TrackerResponse:
        """Set the full in-play tracker state of a character trait."""
        service = TrackerService()
        response = await service.set_trait_state(
            character=character, character_trait=character_trait, data=data
        )
        request.state.audit_description = service.audit_description
        request.state.audit_changes = service.audit_changes
        return response

    @post(
        path=urls.Characters.TRAIT_TRACKER_ACTIONS,
        summary="Apply trait tracker action",
        operation_id="applyTraitTrackerAction",
        description=docs.APPLY_TRAIT_TRACKER_ACTION_DESCRIPTION,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.post_data_update_hook,
        status_code=200,
    )
    async def apply_trait_tracker_action(
        self,
        request: Request,
        character: Character,
        character_trait: CharacterTrait,
        acting_user: User,  # noqa: ARG002
        data: TrackerActionRequest,
    ) -> TrackerResponse:
        """Apply one in-play action to a character trait tracker."""
        service = TrackerService()
        response = await service.apply_trait_action(
            character=character, character_trait=character_trait, data=data
        )
        request.state.audit_operation = AuditOperation.UPDATE
        request.state.audit_description = service.audit_description
        request.state.audit_changes = service.audit_changes
        return response
