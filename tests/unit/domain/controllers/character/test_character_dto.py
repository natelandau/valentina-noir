"""Unit tests for CharacterResponse DTO."""

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


async def test_character_response_from_model_allows_null_player(
    character_factory: "Callable[..., Any]",
) -> None:
    """Verify CharacterResponse serializes an NPC with no player."""
    from vapi.constants import CharacterType
    from vapi.db.sql_models.character import Character
    from vapi.domain.controllers.character.dto import CHARACTER_RESPONSE_PREFETCH, CharacterResponse

    # Given an NPC character with no player
    character = await character_factory(type=CharacterType.NPC, user_player=None)
    refreshed = (
        await Character.filter(id=character.id)
        .prefetch_related(*CHARACTER_RESPONSE_PREFETCH)
        .first()
    )

    # When building the response DTO
    response = CharacterResponse.from_model(refreshed)

    # Then the player id is None
    assert response.user_player_id is None
