"""Character API."""

import asyncio
from typing import Annotated
from uuid import UUID

from litestar import Request  # noqa: TC002
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.constants import CharacterClass, CharacterStatus, CharacterType
from vapi.db.sql_models.campaign import Campaign
from vapi.db.sql_models.character import (
    Character,
    HunterAttributes,
    MageAttributes,
    VampireAttributes,
    WerewolfAttributes,
)
from vapi.db.sql_models.character_sheet import TraitCategory
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CharacterService, CharacterSheetService
from vapi.lib.detail_includes import apply_includes
from vapi.lib.guards import (
    developer_company_user_guard,
    user_active_guard,
    user_character_player_or_storyteller_guard,
)
from vapi.openapi.tags import APITags

from . import docs
from .dto import (
    CHARACTER_RESPONSE_PREFETCH,
    CharacterCreate,
    CharacterDetailResponse,
    CharacterFullSheetDTO,
    CharacterInclude,
    CharacterPatch,
    CharacterResponse,
    FullSheetTraitCategoryDTO,
    get_character_include_prefetch_map,
)


class CharacterController(Controller):
    """Character controller."""

    tags = [APITags.CHARACTERS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "campaign": Provide(deps.provide_campaign_by_id),
        "character": Provide(deps.provide_character_by_id_and_company),
        "developer": Provide(deps.provide_developer_from_request),
    }
    guards = [developer_company_user_guard, user_active_guard]

    @get(
        path=urls.Characters.LIST,
        summary="List characters",
        operation_id="listCharacters",
        description=docs.LIST_CHARACTERS_DESCRIPTION,
        cache=True,
    )
    async def list_characters(  # noqa: PLR0913
        self,
        company: Company,
        campaign: Campaign,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        user_player_id: Annotated[
            UUID, Parameter(description="Show characters played by this user.")
        ]
        | None = None,
        user_creator_id: Annotated[
            UUID, Parameter(description="Show characters created by this user.")
        ]
        | None = None,
        character_class: Annotated[
            CharacterClass, Parameter(description="Show characters of this class.")
        ]
        | None = None,
        character_type: Annotated[
            CharacterType, Parameter(description="Show characters of this type.")
        ]
        | None = None,
        status: Annotated[CharacterStatus, Parameter(description="Show characters of this status.")]
        | None = None,
        is_temporary: Annotated[
            bool, Parameter(description="Filter by temporary characters.")
        ] = False,
    ) -> OffsetPagination[CharacterResponse]:
        """List all characters."""
        filters: dict[str, object] = {
            "company_id": company.id,
            "is_archived": False,
            "campaign_id": campaign.id,
            "is_temporary": is_temporary,
        }

        if user_player_id:
            filters["user_player_id"] = user_player_id
        if user_creator_id:
            filters["user_creator_id"] = user_creator_id
        if character_class:
            filters["character_class"] = character_class
        if character_type:
            filters["type"] = character_type
        if status:
            filters["status"] = status

        qs = Character.filter(**filters)
        count, characters = await asyncio.gather(
            qs.count(),
            qs.offset(offset).limit(limit).prefetch_related(*CHARACTER_RESPONSE_PREFETCH),
        )

        return OffsetPagination[CharacterResponse](
            items=[CharacterResponse.from_model(c) for c in characters],
            limit=limit,
            offset=offset,
            total=count,
        )

    @get(
        path=urls.Characters.DETAIL,
        summary="Get character",
        operation_id="getCharacter",
        description=docs.GET_CHARACTER_DESCRIPTION,
        cache=True,
    )
    async def get_character(
        self,
        character: Character,
        include: list[CharacterInclude] | None = None,
    ) -> CharacterDetailResponse:
        """Get a character by ID with optional embedded children."""
        requested = await apply_includes(character, include, get_character_include_prefetch_map())
        return CharacterDetailResponse.from_model(character, requested)

    @post(
        path=urls.Characters.CREATE,
        summary="Create character",
        operation_id="createCharacter",
        description=docs.CREATE_CHARACTER_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def create_character(
        self,
        company: Company,
        user: User,
        campaign: Campaign,
        data: CharacterCreate,
    ) -> CharacterResponse:
        """Create a new character."""
        character = await Character.create(
            name_first=data.name_first,
            name_last=data.name_last,
            name_nick=data.name_nick,
            character_class=data.character_class,
            type=data.type,
            game_version=data.game_version,
            age=data.age,
            biography=data.biography,
            demeanor=data.demeanor,
            nature=data.nature,
            concept_id=data.concept_id,
            company=company,
            campaign=campaign,
            user_creator=user,
            user_player_id=data.user_player_id or user.id,
        )

        # Create OneToOne attribute rows for class-specific data
        if data.vampire_attributes:
            await VampireAttributes.create(
                character=character,
                clan_id=data.vampire_attributes.clan_id,
                generation=data.vampire_attributes.generation,
                sire=data.vampire_attributes.sire,
                bane_name=data.vampire_attributes.bane_name,
                bane_description=data.vampire_attributes.bane_description,
                compulsion_name=data.vampire_attributes.compulsion_name,
                compulsion_description=data.vampire_attributes.compulsion_description,
            )
        if data.werewolf_attributes:
            await WerewolfAttributes.create(
                character=character,
                tribe_id=data.werewolf_attributes.tribe_id,
                auspice_id=data.werewolf_attributes.auspice_id,
                pack_name=data.werewolf_attributes.pack_name,
            )
        if data.mage_attributes:
            await MageAttributes.create(
                character=character,
                sphere=data.mage_attributes.sphere,
                tradition=data.mage_attributes.tradition,
            )
        if data.hunter_attributes:
            await HunterAttributes.create(
                character=character,
                creed=data.hunter_attributes.creed,
            )

        service = CharacterService()
        await service.prepare_for_save(character)

        if data.traits:
            await service.character_create_trait_to_character_traits(
                character=character,
                trait_create_data=data.traits,
            )

        character = await (
            Character.filter(id=character.id).prefetch_related(*CHARACTER_RESPONSE_PREFETCH).first()
        )

        return CharacterResponse.from_model(character)

    @patch(
        path=urls.Characters.UPDATE,
        summary="Update character",
        operation_id="updateCharacter",
        description=docs.UPDATE_CHARACTER_DESCRIPTION,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.post_data_update_hook,
    )
    async def update_character(
        self,
        character: Character,
        data: CharacterPatch,
        request: "Request",
    ) -> CharacterResponse:
        """Update a character."""
        service = CharacterService()
        changes = await service.apply_patch(character, data)
        await service.prepare_for_save(character)
        await character.save()

        request.state.audit_changes = changes

        character = await (
            Character.filter(id=character.id).prefetch_related(*CHARACTER_RESPONSE_PREFETCH).first()
        )

        return CharacterResponse.from_model(character)

    @delete(
        path=urls.Characters.DELETE,
        summary="Delete character",
        operation_id="deleteCharacter",
        description=docs.DELETE_CHARACTER_DESCRIPTION,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.post_data_update_hook,
    )
    async def delete_character(self, character: Character) -> None:
        """Delete a character."""
        service = CharacterService()
        await service.archive_character(character)

    @get(
        path=urls.Characters.FULL_SHEET,
        summary="Get character full sheet",
        operation_id="getCharacterFullSheet",
        description=docs.GET_CHARACTER_FULL_SHEET_DESCRIPTION,
        cache=True,
    )
    async def get_character_full_sheet(
        self,
        character: Character,
        include_available_traits: Annotated[
            bool,
            Parameter(description="Include available traits for each category and subcategory."),
        ] = False,
    ) -> CharacterFullSheetDTO:
        """Get a character full sheet."""
        svc = CharacterSheetService()
        return await svc.get_character_full_sheet(
            character, include_available_traits=include_available_traits
        )

    @get(
        path=urls.Characters.FULL_SHEET_CATEGORY,
        summary="Get character full sheet category",
        operation_id="getCharacterFullSheetCategory",
        description=docs.GET_CHARACTER_FULL_SHEET_CATEGORY_DESCRIPTION,
        cache=True,
        dependencies={"category": Provide(deps.provide_trait_category_by_id)},
    )
    async def get_character_full_sheet_category(
        self,
        character: Character,
        category: TraitCategory,
        include_available_traits: Annotated[
            bool,
            Parameter(description="Include available traits for this category."),
        ] = False,
    ) -> FullSheetTraitCategoryDTO:
        """Get a single category slice of the character's full sheet."""
        svc = CharacterSheetService()
        return await svc.get_character_full_sheet_category(
            character, category, include_available_traits=include_available_traits
        )
