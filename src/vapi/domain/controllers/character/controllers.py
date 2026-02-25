"""Character API."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from litestar.controller import Controller
from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter
from pydantic import ValidationError as PydanticValidationError

from vapi.constants import CharacterClass, CharacterStatus, CharacterType  # noqa: TC001
from vapi.db.models import Campaign, Character, Company, User
from vapi.domain import deps, hooks, urls
from vapi.domain.handlers import CharacterArchiveHandler
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CharacterService
from vapi.domain.utils import patch_dto_data_internal_objects
from vapi.lib.guards import developer_company_user_guard, user_character_player_or_storyteller_guard
from vapi.openapi.tags import APITags
from vapi.utils.validation import raise_from_pydantic_validation_error

from . import docs, dto


class CharacterController(Controller):
    """Character controller."""

    tags = [APITags.CHARACTERS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "campaign": Provide(deps.provide_campaign_by_id),
        "character": Provide(deps.provide_character_by_id_and_company),
    }
    guards = [developer_company_user_guard]
    return_dto = dto.CharacterResponseDTO

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
            PydanticObjectId, Parameter(description="Show characters played by this user.")
        ]
        | None = None,
        user_creator_id: Annotated[
            PydanticObjectId, Parameter(description="Show characters created by this user.")
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
    ) -> OffsetPagination[Character]:
        """List all characters."""
        query = {
            "company_id": company.id,
            "is_archived": False,
            "campaign_id": campaign.id,
            "is_temporary": False,
        }

        if user_player_id:
            query["user_player_id"] = user_player_id
        if user_creator_id:
            query["user_creator_id"] = user_creator_id
        if character_class:
            query["character_class"] = character_class.name
        if character_type:
            query["type"] = character_type.name
        if status:
            query["status"] = status.name

        count = await Character.find(query).count()
        characters = await Character.find(query).skip(offset).limit(limit).to_list()

        return OffsetPagination[Character](
            items=characters, limit=limit, offset=offset, total=count
        )

    @get(
        path=urls.Characters.DETAIL,
        summary="Get character",
        operation_id="getCharacter",
        description=docs.GET_CHARACTER_DESCRIPTION,
        cache=True,
    )
    async def get_character(self, character: Character) -> Character:
        """Get a character by ID."""
        return character

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
        data: dto.CreateCharacterDTO,  # type: ignore[valid-type]
    ) -> Character:
        """Create a new character."""
        try:
            character = Character(
                **data.model_dump(  # type: ignore[attr-defined]
                    exclude_unset=True,
                    exclude_none=True,
                    exclude={"traits", "user_player_id"},
                ),
                campaign_id=campaign.id,
                company_id=company.id,
                user_creator_id=user.id,
                user_player_id=data.user_player_id or user.id,  # type: ignore[attr-defined]
            )
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        service = CharacterService()
        await service.prepare_for_save(character)

        try:
            await character.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        await service.character_create_trait_to_character_traits(
            character=character,
            trait_create_data=data.traits,  # type: ignore[attr-defined]
        )

        await character.sync()
        return character

    @patch(
        path=urls.Characters.UPDATE,
        summary="Update character",
        operation_id="updateCharacter",
        description=docs.UPDATE_CHARACTER_DESCRIPTION,
        dto=dto.CharacterPatchDTO,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.post_data_update_hook,
    )
    async def update_character(
        self,
        character: Character,
        data: DTOData[Character],
    ) -> Character:
        """Update a character."""
        character, data = await patch_dto_data_internal_objects(original=character, data=data)
        updated_character = data.update_instance(character)

        service = CharacterService()
        await service.prepare_for_save(updated_character)

        try:
            await updated_character.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return updated_character

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
        await CharacterArchiveHandler(character=character).handle()
