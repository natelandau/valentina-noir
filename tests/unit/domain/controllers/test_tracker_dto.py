"""Tests for tracker and health response shapes."""

import msgspec
import pytest

from vapi.constants import DamageType, GameVersion, TrackerType
from vapi.db.sql_models.character import Character, CharacterTrait
from vapi.domain.controllers.character.dto import CHARACTER_RESPONSE_PREFETCH, CharacterResponse
from vapi.domain.controllers.character_health.dto import HealthResponse
from vapi.domain.controllers.character_trait.dto import (
    CHARACTER_TRAIT_PREFETCH,
    CharacterTraitResponse,
    CounterTrackerResponse,
    StainsTrackerResponse,
)

pytestmark = pytest.mark.anyio


async def _response(ct: CharacterTrait) -> CharacterTraitResponse:
    """Reload a character trait with the response prefetch and serialize it."""
    loaded = (
        await CharacterTrait.filter(id=ct.id).prefetch_related(*CHARACTER_TRAIT_PREFETCH).first()
    )
    character = await Character.get(id=ct.character_id)
    return CharacterTraitResponse.from_model(loaded, game_version=character.game_version)


async def test_counter_tracker_reports_current(
    character_factory, trait_factory, character_trait_factory
):
    """A counter tracker reports the trait value as size and the unspent remainder."""
    # Given a V4 Willpower-like trait with a counter tracker, value 6, spent 2
    character = await character_factory(game_version=GameVersion.V4)
    trait = await trait_factory(tracker_type_v4=TrackerType.COUNTER)
    ct = await character_trait_factory(character=character, trait=trait, value=6, tracker_spent=2)

    # When the response is built
    response = await _response(ct)

    # Then the counter shows size 6 and current 4
    assert response.tracker == CounterTrackerResponse(size=6, current=4)


async def test_tracker_null_for_other_version(
    character_factory, trait_factory, character_trait_factory
):
    """A V4-only tracker is null on a V5 character."""
    # Given a trait with a tracker for V4 only, on a V5 character
    character = await character_factory(game_version=GameVersion.V5)
    trait = await trait_factory(tracker_type_v4=TrackerType.COUNTER)
    ct = await character_trait_factory(character=character, trait=trait, value=6)

    # When the response is built
    response = await _response(ct)

    # Then there is no tracker
    assert response.tracker is None


async def test_tracker_null_for_custom_trait(
    character_factory, trait_factory, character_trait_factory
):
    """A custom trait never has a tracker."""
    # Given a custom trait that carries a tracker type
    character = await character_factory(game_version=GameVersion.V4)
    trait = await trait_factory(
        tracker_type_v4=TrackerType.COUNTER, custom_for_character_id=character.id
    )
    ct = await character_trait_factory(character=character, trait=trait, value=6)

    # When the response is built
    response = await _response(ct)

    # Then there is no tracker
    assert response.tracker is None


async def test_stains_tracker_capacity(character_factory, trait_factory, character_trait_factory):
    """Stains capacity is the empty Humanity boxes and stains beyond it impair."""
    # Given Humanity 7 with 4 stains
    character = await character_factory(game_version=GameVersion.V5)
    trait = await trait_factory(tracker_type_v5=TrackerType.STAINS)
    ct = await character_trait_factory(character=character, trait=trait, value=7, tracker_stains=4)

    # When the response is built
    response = await _response(ct)

    # Then capacity is 3 and the character is impaired
    assert response.tracker == StainsTrackerResponse(
        humanity=7, stain_capacity=3, stains=4, is_impaired=True
    )


async def test_damage_tracker_boxes(character_factory, trait_factory, character_trait_factory):
    """A V5 damage tracker renders boxes and impairs when every box is marked."""
    # Given Willpower 3 with 2 superficial and 1 aggravated
    character = await character_factory(game_version=GameVersion.V5)
    trait = await trait_factory(tracker_type_v5=TrackerType.DAMAGE)
    ct = await character_trait_factory(
        character=character, trait=trait, value=3, tracker_superficial=2, tracker_aggravated=1
    )

    # When the response is built
    response = await _response(ct)

    # Then the boxes are in severity order and the track is impaired
    assert msgspec.to_builtins(response.tracker) == {
        "type": "DAMAGE",
        "size": 3,
        "superficial": 2,
        "aggravated": 1,
        "boxes": ["AGGRAVATED", "SUPERFICIAL", "SUPERFICIAL"],
        "is_impaired": True,
        "bashing": None,
        "lethal": None,
        "levels": None,
        "current_penalty": None,
    }


async def test_v5_health_response_has_no_v4_fields(character_factory, character_health_factory):
    """V5 health leaves the V4-only fields null."""
    # Given a V5 character with 1 superficial and 1 aggravated
    character = await character_factory(game_version=GameVersion.V5, health=False)
    health = await character_health_factory(
        character=character, size=3, superficial=1, aggravated=1
    )

    # When the health response is built
    response = HealthResponse.from_model(health, game_version=GameVersion.V5)

    # Then V4 fields are null and boxes are padded to the size
    assert response.size == 3
    assert response.boxes == [DamageType.AGGRAVATED, DamageType.SUPERFICIAL, None]
    assert response.is_impaired is False
    assert response.bashing is None
    assert response.lethal is None
    assert response.levels is None
    assert response.current_penalty is None


async def test_v4_health_response_levels_and_penalty(character_factory, character_health_factory):
    """V4 health reports levels, bashing, lethal, and the current penalty."""
    # Given a V4 character with 2 bashing and 1 lethal
    character = await character_factory(game_version=GameVersion.V4, health=False)
    health = await character_health_factory(character=character, size=7, bashing=2, lethal=1)

    # When the health response is built
    response = HealthResponse.from_model(health, game_version=GameVersion.V4)

    # Then three levels are marked, most severe first, with the Injured penalty
    assert response.size == 7
    assert response.bashing == 2
    assert response.lethal == 1
    assert response.levels is not None
    assert [(lv.name, lv.penalty, lv.mark) for lv in response.levels[:4]] == [
        ("Bruised", 0, DamageType.LETHAL),
        ("Hurt", -1, DamageType.BASHING),
        ("Injured", -1, DamageType.BASHING),
        ("Wounded", -2, None),
    ]
    assert response.current_penalty == -1
    assert response.is_impaired is False


async def test_v4_health_incapacitated_is_impaired(character_factory, character_health_factory):
    """V4 health is impaired when Incapacitated is marked."""
    # Given a V4 character with every level marked
    character = await character_factory(game_version=GameVersion.V4, health=False)
    health = await character_health_factory(character=character, size=7, bashing=7)

    # When the health response is built
    response = HealthResponse.from_model(health, game_version=GameVersion.V4)

    # Then it is impaired with no penalty
    assert response.is_impaired is True
    assert response.current_penalty is None


async def test_character_response_embeds_health(character_factory):
    """The character response embeds the health track."""
    # Given a V5 character
    character = await character_factory(game_version=GameVersion.V5)
    loaded = (
        await Character.filter(id=character.id)
        .prefetch_related(*CHARACTER_RESPONSE_PREFETCH)
        .first()
    )

    # When the character response is built
    response = CharacterResponse.from_model(loaded)

    # Then health is embedded with the V5 base size
    assert response.health.size == 3
    assert msgspec.to_builtins(response.health)["type"] == "DAMAGE"


async def test_v4_health_size_matches_levels_with_extra_levels(
    character_factory, character_health_factory
):
    """V4 health reports the stored size, which matches its level count."""
    # Given a V4 character with two extra levels
    character = await character_factory(game_version=GameVersion.V4, health=False)
    health = await character_health_factory(character=character, size=9, extra_levels=2)

    # When the health response is built
    response = HealthResponse.from_model(health, game_version=GameVersion.V4)

    # Then the size and the levels agree
    assert response.size == 9
    assert response.levels is not None
    assert len(response.levels) == 9
    assert len(response.boxes) == 9
