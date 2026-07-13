"""Unit tests for CharacterResponse DTO."""

from datetime import date
from typing import TYPE_CHECKING, Any

import msgspec
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


async def test_character_response_serializes_date_of_birth(
    character_factory: "Callable[..., Any]",
) -> None:
    """Verify CharacterResponse carries the date of birth through JSON round-trip."""
    from vapi.db.sql_models.character import Character
    from vapi.domain.controllers.character.dto import CHARACTER_RESPONSE_PREFETCH, CharacterResponse

    # Given a character with a date of birth
    character = await character_factory(date_of_birth=date(1888, 6, 15))
    refreshed = (
        await Character.filter(id=character.id)
        .prefetch_related(*CHARACTER_RESPONSE_PREFETCH)
        .first()
    )

    # When building the response DTO and round-tripping through JSON
    response = CharacterResponse.from_model(refreshed)
    decoded = msgspec.json.decode(msgspec.json.encode(response), type=CharacterResponse)

    # Then the date of birth survives serialization
    assert decoded.date_of_birth == date(1888, 6, 15)


async def test_character_response_allows_null_date_of_birth(
    character_factory: "Callable[..., Any]",
) -> None:
    """Verify CharacterResponse serializes a character with no date of birth as null."""
    from vapi.db.sql_models.character import Character
    from vapi.domain.controllers.character.dto import CHARACTER_RESPONSE_PREFETCH, CharacterResponse

    # Given a character with no date of birth
    character = await character_factory()
    refreshed = (
        await Character.filter(id=character.id)
        .prefetch_related(*CHARACTER_RESPONSE_PREFETCH)
        .first()
    )

    # When building the response DTO and round-tripping through JSON
    response = CharacterResponse.from_model(refreshed)
    decoded = msgspec.json.decode(msgspec.json.encode(response), type=CharacterResponse)

    # Then the date of birth is None after surviving JSON decode validation
    assert decoded.date_of_birth is None


async def test_character_response_from_model_allows_null_player(
    character_factory: "Callable[..., Any]",
) -> None:
    """Verify CharacterResponse serializes and deserializes an NPC with no player."""
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

    # When building the response DTO and round-tripping through JSON
    # (msgspec only validates types on decode, not on Python construction,
    # so a round-trip is required to prove the field is truly nullable)
    response = CharacterResponse.from_model(refreshed)
    payload = msgspec.json.encode(response)
    decoded = msgspec.json.decode(payload, type=CharacterResponse)

    # Then the player id is None after surviving JSON decode validation
    assert decoded.user_player_id is None
