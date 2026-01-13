"""Hunter specials controller. Manages hunter edges and perks for a character."""

from __future__ import annotations

from typing import Annotated

from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, post
from litestar.params import Parameter

from vapi.db.models import (
    Character,  # noqa: TC001
    HunterEdge,  # noqa: TC001
    HunterEdgePerk,  # noqa: TC001
)
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CharacterEdgeService
from vapi.lib.guards import developer_company_user_guard, user_character_player_or_storyteller_guard
from vapi.openapi.tags import APITags

from . import dto  # noqa: TC001


class HunterSpecialsController(Controller):
    """Hunter edge controller."""

    tags = [APITags.CHARACTERS_SPECIAL_TRAITS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "character": Provide(deps.provide_character_by_id_and_company),
        "edge": Provide(deps.provide_hunter_edge_by_id),
        "perk": Provide(deps.provide_hunter_edge_perk_by_id),
    }
    guards = [developer_company_user_guard]

    @get(
        path=urls.Characters.EDGES,
        summary="List hunter edges",
        operation_id="listCharacterHunterEdges",
        description="Retrieve a paginated list of hunter edges for a character.",
        cache=True,
    )
    async def list_hunter_edges(
        self,
        character: Character,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[dto.CharacterEdgeAndPerksDTO]:
        """List all hunter edges."""
        service = CharacterEdgeService()

        edges_to_return = []
        if character.hunter_attributes and character.hunter_attributes.edges:
            for character_edge in character.hunter_attributes.edges:
                edge = await service.get_edge_and_perks_dto_by_id(character_edge.edge_id, character)
                edges_to_return.append(edge)

        return OffsetPagination(
            items=edges_to_return,
            limit=limit,
            offset=offset,
            total=len(edges_to_return),
        )

    @get(
        path=urls.Characters.EDGE_DETAIL,
        summary="Get character edge and perks",
        operation_id="getCharacterHunterEdge",
        description="Retrieve a specific character's edge and its perks.",
        cache=True,
    )
    async def get_hunter_edge(
        self, *, character: Character, edge: HunterEdge
    ) -> dto.CharacterEdgeAndPerksDTO:
        """Get a character edge and its perks."""
        service = CharacterEdgeService()
        return await service.get_edge_and_perks_dto_by_id(
            edge_id=edge.id, character=character, raise_on_not_found=True
        )

    @get(
        path=urls.Characters.EDGE_PERKS,
        summary="List hunter edge perks",
        operation_id="listCharacterHunterEdgePerks",
        description="Retrieve a paginated list of hunter edge perks for a character.",
        cache=True,
    )
    async def list_hunter_edge_perks(
        self,
        character: Character,
        edge: HunterEdge,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[dto.CharacterPerkDTO]:
        """List all hunter edge perks."""
        service = CharacterEdgeService()
        character_edge_dto = await service.get_edge_and_perks_dto_by_id(
            edge_id=edge.id, character=character, raise_on_not_found=True
        )

        return OffsetPagination(
            items=character_edge_dto.perks,
            limit=limit,
            offset=offset,
            total=len(character_edge_dto.perks),
        )

    @get(
        path=urls.Characters.EDGE_PERK_DETAIL,
        summary="Get hunter edge perk",
        operation_id="getCharacterHunterEdgePerk",
        description="Retrieve a specific hunter edge perk.",
        cache=True,
    )
    async def get_hunter_edge_perk(
        self, *, character: Character, perk: HunterEdgePerk
    ) -> dto.CharacterPerkDTO:
        """Get a hunter edge perk."""
        service = CharacterEdgeService()
        return await service.get_perk_dto_by_id(
            perk_id=perk.id, character=character, raise_on_not_found=True
        )

    @post(
        path=urls.Characters.EDGE_ADD,
        summary="Add a hunter edge to a character",
        operation_id="addCharacterHunterEdge",
        description="Add a hunter edge to a character.",
        cache=False,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def add_hunter_edge(
        self,
        character: Character,
        edge: HunterEdge,
    ) -> dto.CharacterEdgeAndPerksDTO:
        """Add a hunter edge to a character."""
        service = CharacterEdgeService()
        return await service.add_edge_to_character(edge=edge, character=character)

    @delete(
        path=urls.Characters.EDGE_REMOVE,
        summary="Remove a hunter edge from a character",
        operation_id="removeCharacterHunterEdge",
        description="Remove a hunter edge from a character.",
        cache=False,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def remove_hunter_edge(
        self,
        character: Character,
        edge: HunterEdge,
    ) -> None:
        """Remove a hunter edge from a character."""
        service = CharacterEdgeService()
        await service.remove_edge_from_character(edge_id=edge.id, character=character)

    @post(
        path=urls.Characters.EDGE_PERK_ADD,
        summary="Add a hunter edge perk to a character",
        operation_id="addCharacterHunterEdgePerk",
        description="Add a hunter edge perk to a character.",
        cache=False,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def add_hunter_edge_perk(
        self,
        character: Character,
        edge: HunterEdge,
        perk: HunterEdgePerk,
    ) -> dto.CharacterEdgeAndPerksDTO:
        """Add a hunter edge perk to a character."""
        service = CharacterEdgeService()
        return await service.add_perk_to_edge(perk=perk, edge=edge, character=character)

    @delete(
        path=urls.Characters.EDGE_PERK_REMOVE,
        summary="Remove a hunter edge perk from a character",
        operation_id="removeCharacterHunterEdgePerk",
        description="Remove a hunter edge perk from a character.",
        cache=False,
        guards=[user_character_player_or_storyteller_guard],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def remove_hunter_edge_perk(
        self, character: Character, edge: HunterEdge, perk: HunterEdgePerk
    ) -> None:
        """Remove a hunter edge perk from a character."""
        service = CharacterEdgeService()

        await service.remove_perk_from_edge(perk=perk, edge=edge, character=character)
