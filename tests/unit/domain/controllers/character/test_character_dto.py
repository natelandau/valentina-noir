"""Unit tests for CharacterResponse DTO."""

from datetime import date
from typing import TYPE_CHECKING, Any

import msgspec
import pytest

from vapi.constants import CharacterStatus

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


async def _response_for(character_id: Any) -> Any:
    """Build a CharacterResponse the way the controllers do, round-tripped through JSON.

    msgspec validates types only on decode, so the round-trip proves nullable fields really are.
    """
    from vapi.db.sql_models.character import Character
    from vapi.domain.controllers.character.dto import CHARACTER_RESPONSE_PREFETCH, CharacterResponse

    refreshed = (
        await Character.filter(id=character_id)
        .prefetch_related(*CHARACTER_RESPONSE_PREFETCH)
        .first()
    )
    response = CharacterResponse.from_model(refreshed)
    return msgspec.json.decode(msgspec.json.encode(response), type=CharacterResponse)


async def test_character_response_serializes_date_of_birth(
    character_factory: "Callable[..., Any]",
) -> None:
    """Verify CharacterResponse carries the date of birth through JSON round-trip."""
    # Given a character with a date of birth
    character = await character_factory(date_of_birth=date(1888, 6, 15))

    # When building the response DTO and round-tripping through JSON
    decoded = await _response_for(character.id)

    # Then the date of birth survives serialization
    assert decoded.date_of_birth == date(1888, 6, 15)


async def test_character_response_allows_null_date_of_birth(
    character_factory: "Callable[..., Any]",
) -> None:
    """Verify CharacterResponse serializes a character with no date of birth as null."""
    # Given a character with no date of birth
    character = await character_factory()

    # When building the response DTO and round-tripping through JSON
    decoded = await _response_for(character.id)

    # Then the date of birth is None after surviving JSON decode validation
    assert decoded.date_of_birth is None


@pytest.mark.parametrize(
    ("status", "in_game_date", "date_of_birth", "expected"),
    [
        (CharacterStatus.ALIVE, date(1986, 6, 1), date(1960, 3, 15), 26),
        (CharacterStatus.ALIVE, date(2003, 1, 1), date(1960, 3, 15), 42),
        (CharacterStatus.ALIVE, date(1986, 6, 1), None, 99),
        (CharacterStatus.ALIVE, None, date(1960, 3, 15), 99),
        (CharacterStatus.ALIVE, None, None, 99),
        (CharacterStatus.DEAD, date(2003, 1, 1), date(1960, 3, 15), 99),
    ],
)
async def test_character_response_age(
    character_factory: "Callable[..., Any]",
    campaign_factory: "Callable[..., Any]",
    company_factory: "Callable[..., Any]",
    status: CharacterStatus,
    in_game_date: date | None,
    date_of_birth: date | None,
    expected: int,
) -> None:
    """Verify age is computed for a living character with both dates, else the stored age."""
    # Given a character with a stored age of 99
    company = await company_factory()
    campaign = await campaign_factory(company=company, in_game_date=in_game_date)
    character = await character_factory(
        company=company, campaign=campaign, date_of_birth=date_of_birth, age=99, status=status
    )

    # When building the response
    decoded = await _response_for(character.id)

    # Then the age is computed from both dates, or falls back to the stored age
    assert decoded.age == expected


async def test_current_age_uses_stored_age_when_campaign_not_loaded(
    character_factory: "Callable[..., Any]",
    campaign_factory: "Callable[..., Any]",
    company_factory: "Callable[..., Any]",
) -> None:
    """Verify an unloaded campaign falls back to the stored age instead of raising."""
    from vapi.db.sql_models.character import Character

    # Given a character with both dates, loaded without its campaign
    company = await company_factory()
    campaign = await campaign_factory(company=company, in_game_date=date(1986, 6, 1))
    character = await character_factory(
        company=company, campaign=campaign, date_of_birth=date(1960, 3, 15), age=31
    )
    unloaded = await Character.get(id=character.id)

    # When reading the age
    age = unloaded.current_age

    # Then the stored age is returned
    assert age == 31


async def test_character_response_from_model_allows_null_player(
    character_factory: "Callable[..., Any]",
) -> None:
    """Verify CharacterResponse serializes and deserializes an NPC with no player."""
    from vapi.constants import CharacterType

    # Given an NPC character with no player
    character = await character_factory(type=CharacterType.NPC, user_player=None)

    # When building the response DTO and round-tripping through JSON
    decoded = await _response_for(character.id)

    # Then the player id is None after surviving JSON decode validation
    assert decoded.user_player_id is None


async def test_character_detail_include_traits_loads_specialties(
    character_factory: "Callable[..., Any]",
    character_trait_factory: "Callable[..., Any]",
    character_trait_specialty_factory: "Callable[..., Any]",
) -> None:
    """Verify include=traits embeds each trait's specialties."""
    from vapi.db.sql_models.character import Character
    from vapi.db.sql_models.character_sheet import Trait
    from vapi.domain.controllers.character.dto import (
        CHARACTER_RESPONSE_PREFETCH,
        CharacterDetailResponse,
        CharacterInclude,
        get_character_include_prefetch_map,
    )
    from vapi.lib.detail_includes import apply_includes

    # Given a character with an ability that has a specialty
    character = await character_factory()
    trait = await Trait.filter(
        sheet_section__name="Abilities", is_archived=False, custom_for_character_id=None
    ).first()
    char_trait = await character_trait_factory(character=character, trait=trait, value=1)
    await character_trait_specialty_factory(character_trait=char_trait, name="Sniping")
    loaded = (
        await Character.filter(id=character.id)
        .prefetch_related(*CHARACTER_RESPONSE_PREFETCH)
        .first()
    )

    # When applying the traits include and building the detail response
    requested = await apply_includes(
        loaded, [CharacterInclude.TRAITS], get_character_include_prefetch_map()
    )
    response = CharacterDetailResponse.from_model(loaded, requested)

    # Then the embedded trait lists its specialty
    assert [sp.name for sp in response.traits[0].specialties] == ["Sniping"]


async def test_character_detail_include_traits_loads_gift_tribe_and_auspice(
    character_factory: "Callable[..., Any]",
    character_trait_factory: "Callable[..., Any]",
) -> None:
    """Verify include=traits embeds a werewolf gift's tribe and auspice."""
    from vapi.db.sql_models.character import Character
    from vapi.db.sql_models.character_sheet import Trait
    from vapi.domain.controllers.character.dto import (
        CHARACTER_RESPONSE_PREFETCH,
        CharacterDetailResponse,
        CharacterInclude,
        get_character_include_prefetch_map,
    )
    from vapi.lib.detail_includes import apply_includes

    # Given a character that owns a tribe gift and an auspice gift
    character = await character_factory()
    tribe_gift = await Trait.filter(gift_tribe_id__isnull=False, is_archived=False).first()
    auspice_gift = await Trait.filter(gift_auspice_id__isnull=False, is_archived=False).first()
    await character_trait_factory(character=character, trait=tribe_gift, value=1)
    await character_trait_factory(character=character, trait=auspice_gift, value=1)
    loaded = (
        await Character.filter(id=character.id)
        .prefetch_related(*CHARACTER_RESPONSE_PREFETCH)
        .first()
    )

    # When applying the traits include and building the detail response
    requested = await apply_includes(
        loaded, [CharacterInclude.TRAITS], get_character_include_prefetch_map()
    )
    response = CharacterDetailResponse.from_model(loaded, requested)

    # Then each gift names its tribe or auspice
    gifts = {t.trait.id: t.trait.gift_attributes for t in response.traits}
    assert gifts[tribe_gift.id].tribe_id == tribe_gift.gift_tribe_id  # ty:ignore[missing-attribute]
    assert gifts[auspice_gift.id].auspice_id == auspice_gift.gift_auspice_id  # ty:ignore[missing-attribute]
