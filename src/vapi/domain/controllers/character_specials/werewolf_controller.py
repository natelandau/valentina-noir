"""Werewolf specials controller. Manages werewolf gifts and rites for a character."""

from __future__ import annotations

from typing import Annotated

from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, post
from litestar.params import Parameter

from vapi.db.models import (
    Character,  # noqa: TC001
    WerewolfGift,  # noqa: TC001
    WerewolfRite,  # noqa: TC001
)
from vapi.domain import deps, hooks, urls
from vapi.domain.controllers.character_blueprint import dto as blueprint_dto
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CharacterGiftsService, CharacterRitesService
from vapi.lib.guards import developer_company_user_guard, user_character_player_or_storyteller_guard
from vapi.openapi.tags import APITags

from . import docs


class WerewolfSpecialsController(Controller):
    """Werewolf controller."""

    tags = [APITags.CHARACTERS_SPECIAL_TRAITS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "character": Provide(deps.provide_character_by_id_and_company),
        "gift": Provide(deps.provide_werewolf_gift_by_id),
        "rite": Provide(deps.provide_werewolf_rite_by_id),
    }
    guards = [developer_company_user_guard]

    ## GIFT RELATED ENDPOINTS
    @get(
        path=urls.Characters.GIFTS,
        summary="List werewolf gifts",
        operation_id="listCharacterWerewolfGifts",
        description=docs.LIST_WEREWOLF_GIFTS_DESCRIPTION,
        cache=True,
        return_dto=blueprint_dto.WerewolfGiftDTO,
    )
    async def list_werewolf_gifts(
        self,
        character: Character,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[WerewolfGift]:
        """List all werewolf gifts."""
        service = CharacterGiftsService()
        all_gifts = await service.fetch_all_gifts_for_character(character)
        total = len(all_gifts)
        return OffsetPagination(
            items=all_gifts,
            limit=limit,
            offset=offset,
            total=total,
        )

    @get(
        path=urls.Characters.GIFT_DETAIL,
        summary="Get werewolf gift",
        operation_id="getCharacterWerewolfGift",
        description=docs.GET_WEREWOLF_GIFT_DESCRIPTION,
        cache=True,
        return_dto=blueprint_dto.WerewolfGiftDTO,
    )
    async def get_werewolf_gift(self, character: Character, gift: WerewolfGift) -> WerewolfGift:
        """Get a werewolf gift by ID."""
        service = CharacterGiftsService()
        return await service.fetch_gift_from_character(
            gift=gift, character=character, raise_on_not_found=True
        )

    @post(
        path=urls.Characters.GIFT_ADD,
        summary="Add a werewolf gift to a character",
        operation_id="addCharacterWerewolfGift",
        description=docs.ADD_WEREWOLF_GIFT_DESCRIPTION,
        return_dto=blueprint_dto.WerewolfGiftDTO,
        cache=False,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def add_werewolf_gift(self, character: Character, gift: WerewolfGift) -> WerewolfGift:
        """Add a werewolf gift to a character."""
        service = CharacterGiftsService()
        await service.add_gift_to_character(gift=gift, character=character)

        return gift

    @delete(
        path=urls.Characters.GIFT_REMOVE,
        summary="Remove a werewolf gift from a character",
        operation_id="removeCharacterWerewolfGift",
        description=docs.REMOVE_WEREWOLF_GIFT_DESCRIPTION,
        cache=False,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def remove_werewolf_gift(self, character: Character, gift: WerewolfGift) -> None:
        """Remove a werewolf gift from a character."""
        service = CharacterGiftsService()
        await service.remove_gift_from_character(gift=gift, character=character)

    ## RITE RELATED ENDPOINTS
    @get(
        path=urls.Characters.RITES,
        summary="List werewolf rites",
        operation_id="listCharacterWerewolfRites",
        description=docs.LIST_WEREWOLF_RITES_DESCRIPTION,
        cache=True,
        return_dto=blueprint_dto.WerewolfRiteDTO,
    )
    async def list_werewolf_rites(
        self,
        character: Character,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[WerewolfRite]:
        """List all werewolf rites."""
        service = CharacterRitesService()
        all_rites = await service.fetch_all_rites_for_character(character)
        return OffsetPagination(items=all_rites, limit=limit, offset=offset, total=len(all_rites))

    @get(
        path=urls.Characters.RITE_DETAIL,
        summary="Get werewolf rite",
        operation_id="getCharacterWerewolfRite",
        description=docs.GET_WEREWOLF_RITE_DESCRIPTION,
        cache=True,
        return_dto=blueprint_dto.WerewolfRiteDTO,
    )
    async def get_werewolf_rite(self, character: Character, rite: WerewolfRite) -> WerewolfRite:
        """Get a werewolf rite by ID."""
        service = CharacterRitesService()
        return await service.fetch_rite_from_character(
            rite=rite, character=character, raise_on_not_found=True
        )

    @post(
        path=urls.Characters.RITE_ADD,
        summary="Add a werewolf rite to a character",
        operation_id="addCharacterWerewolfRite",
        description=docs.ADD_WEREWOLF_RITE_DESCRIPTION,
        return_dto=blueprint_dto.WerewolfRiteDTO,
        cache=False,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def add_werewolf_rite(self, character: Character, rite: WerewolfRite) -> WerewolfRite:
        """Add a werewolf rite to a character."""
        service = CharacterRitesService()
        await service.add_rite_to_character(rite=rite, character=character)

        return rite

    @delete(
        path=urls.Characters.RITE_REMOVE,
        summary="Remove a werewolf rite from a character",
        operation_id="removeCharacterWerewolfRite",
        description=docs.REMOVE_WEREWOLF_RITE_DESCRIPTION,
        cache=False,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def remove_werewolf_rite(self, character: Character, rite: WerewolfRite) -> None:
        """Remove a werewolf rite from a character."""
        service = CharacterRitesService()
        await service.remove_rite_from_character(rite=rite, character=character)
