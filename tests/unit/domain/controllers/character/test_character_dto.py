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


async def _response_for(character_id: Any) -> Any:
    """Build a CharacterResponse the way the controllers do, round-tripped through JSON."""
    from vapi.db.sql_models.character import Character
    from vapi.domain.controllers.character.dto import CHARACTER_RESPONSE_PREFETCH, CharacterResponse

    refreshed = (
        await Character.filter(id=character_id)
        .prefetch_related(*CHARACTER_RESPONSE_PREFETCH)
        .first()
    )
    response = CharacterResponse.from_model(refreshed)
    return msgspec.json.decode(msgspec.json.encode(response), type=CharacterResponse)


async def test_character_response_derives_age_from_birth_year_and_campaign_date(
    character_factory: "Callable[..., Any]",
    campaign_factory: "Callable[..., Any]",
    company_factory: "Callable[..., Any]",
) -> None:
    """Verify age is measured in the campaign's in-game year and advances with it."""
    # Given a character born in 1960 in a campaign set in 1986, with a stale stored age
    company = await company_factory()
    campaign = await campaign_factory(company=company, in_game_date=date(1986, 6, 1))
    character = await character_factory(company=company, campaign=campaign, birth_year=1960, age=99)

    # When building the response
    decoded = await _response_for(character.id)

    # Then the age comes from the birth year, not the stored age
    assert decoded.birth_year == 1960
    assert decoded.age == 26

    # When the campaign moves forward to 2003
    campaign.in_game_date = date(2003, 1, 1)
    await campaign.save()
    decoded = await _response_for(character.id)

    # Then the character has aged with it
    assert decoded.age == 43


async def test_character_response_falls_back_to_stored_age_without_birth_year(
    character_factory: "Callable[..., Any]",
) -> None:
    """Verify a character with no birth year or date of birth keeps its stored age."""
    # Given a character with only a stored age
    character = await character_factory(age=31)

    # When building the response
    decoded = await _response_for(character.id)

    # Then the stored age is returned unchanged
    assert decoded.birth_year is None
    assert decoded.age == 31


async def test_character_response_counts_birthday_from_date_of_birth(
    character_factory: "Callable[..., Any]",
    campaign_factory: "Callable[..., Any]",
    company_factory: "Callable[..., Any]",
) -> None:
    """Verify a full date of birth gives the exact age on the campaign's in-game date."""
    # Given a character born 15 March 1960 in a campaign set the day before their birthday
    company = await company_factory()
    campaign = await campaign_factory(company=company, in_game_date=date(1986, 3, 14))
    character = await character_factory(
        company=company,
        campaign=campaign,
        date_of_birth=date(1960, 3, 15),
        birth_year=1960,
    )

    # When building the response
    decoded = await _response_for(character.id)

    # Then the birthday has not yet counted
    assert decoded.age == 25


async def test_character_response_uses_today_without_campaign_date(
    character_factory: "Callable[..., Any]",
) -> None:
    """Verify age is measured on today's date when the campaign has no in-game date."""
    from vapi.utils.time import time_now

    # Given a character born in 1960 in a campaign with no in-game date
    character = await character_factory(birth_year=1960)

    # When building the response
    decoded = await _response_for(character.id)

    # Then the age is measured against the current year
    assert decoded.age == time_now().year - 1960


@pytest.mark.parametrize("birth_year", [-10000, 10000])
async def test_character_create_rejects_birth_year_out_of_range(birth_year: int) -> None:
    """Verify a birth year outside -9999 to 9999 fails request validation."""
    from vapi.domain.controllers.character.dto import CharacterCreate

    # Given a create body with an out-of-range birth year
    body = {
        "name_first": "Ada",
        "name_last": "Byron",
        "character_class": "MORTAL",
        "game_version": "V5",
        "campaign_id": "01a1db9f-59c9-771b-af93-34a8b1c15bd0",
        "birth_year": birth_year,
    }

    # When / Then decoding it is rejected
    with pytest.raises(msgspec.ValidationError):
        msgspec.json.decode(msgspec.json.encode(body), type=CharacterCreate)


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
