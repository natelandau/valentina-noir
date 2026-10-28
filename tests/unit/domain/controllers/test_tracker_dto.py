"""Tests for tracker and health response shapes."""

import msgspec
import pytest

from vapi.constants import CharacterClass, GameVersion, TrackerType
from vapi.db.sql_models.character import Character, CharacterTrait
from vapi.domain.controllers.character.dto import CHARACTER_RESPONSE_PREFETCH, CharacterResponse
from vapi.domain.controllers.character_health.dto import (
    HealthLevelResponse,
    HealthResponse,
    HealthStateSet,
)
from vapi.domain.controllers.character_trait.dto import (
    CHARACTER_TRAIT_PREFETCH,
    CharacterTraitResponse,
    CounterTrackerResponse,
    StainsTrackerResponse,
    TrackerStateSet,
)

pytestmark = pytest.mark.anyio


async def _response(ct: CharacterTrait) -> CharacterTraitResponse:
    """Reload a character trait with the response prefetch and serialize it."""
    loaded = (
        await CharacterTrait.filter(id=ct.id).prefetch_related(*CHARACTER_TRAIT_PREFETCH).first()
    )
    character = await Character.get(id=ct.character_id)
    return CharacterTraitResponse.from_model(loaded, character=character)


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
    """Stains capacity is the empty Humanity boxes and stains may exceed it."""
    # Given a V5 vampire with Humanity 7 and 4 stains
    character = await character_factory(
        game_version=GameVersion.V5, character_class=CharacterClass.VAMPIRE
    )
    trait = await trait_factory(tracker_type_v5=TrackerType.STAINS)
    ct = await character_trait_factory(character=character, trait=trait, value=7, tracker_stains=4)

    # When the response is built
    response = await _response(ct)

    # Then capacity is 3 and all four stains are kept
    assert response.tracker == StainsTrackerResponse(humanity=7, stain_capacity=3, stains=4)


async def test_stains_trait_is_counter_for_non_vampire(
    character_factory, trait_factory, character_trait_factory
):
    """A stains trait tracks a spend/gain counter for a character who is not a vampire."""
    # Given a V5 mortal with a stains trait at 7 and 1 spent
    character = await character_factory(game_version=GameVersion.V5)
    trait = await trait_factory(tracker_type_v5=TrackerType.STAINS)
    ct = await character_trait_factory(character=character, trait=trait, value=7, tracker_spent=1)

    # When the response is built
    response = await _response(ct)

    # Then the tracker is a counter
    assert response.tracker == CounterTrackerResponse(size=7, current=6)


@pytest.mark.parametrize("damage", [0, 3, 4])
async def test_v5_health_response(character_factory, character_health_factory, damage):
    """V5 health reports its damage and leaves the V4-only levels null."""
    # Given a V5 character with some damage
    character = await character_factory(game_version=GameVersion.V5, health=False)
    health = await character_health_factory(character=character, size=4, damage=damage)

    # When the health response is built
    response = HealthResponse.from_model(health, character=character)

    # Then only size, damage, and extra levels are reported
    assert msgspec.to_builtins(response) == {
        "type": "DAMAGE",
        "size": 4,
        "damage": damage,
        "extra_levels": 0,
        "levels": None,
    }


async def test_v4_health_response_marks_levels(character_factory, character_health_factory):
    """V4 health marks levels from the top down."""
    # Given a V4 character with 3 damage
    character = await character_factory(game_version=GameVersion.V4, health=False)
    health = await character_health_factory(character=character, size=7, damage=3)

    # When the health response is built
    response = HealthResponse.from_model(health, character=character)

    # Then the first three levels are marked
    assert response.damage == 3
    assert response.levels is not None
    assert response.levels[:4] == [
        HealthLevelResponse(name="Bruised", marked=True),
        HealthLevelResponse(name="Hurt", marked=True),
        HealthLevelResponse(name="Injured", marked=True),
        HealthLevelResponse(name="Wounded", marked=False),
    ]


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
    response = HealthResponse.from_model(health, character=character)

    # Then the size and the levels agree
    assert response.size == 9
    assert response.levels is not None
    assert len(response.levels) == 9


@pytest.mark.parametrize("field", ["superficial", "aggravated", "bashing", "lethal"])
def test_health_state_set_rejects_unknown_fields(field: str) -> None:
    """Verify a health body with a field other than damage or extra_levels is rejected."""
    # Given a body with a typed damage field
    body = msgspec.json.encode({field: 2})

    # When / Then decoding it fails
    with pytest.raises(msgspec.ValidationError, match=field):
        msgspec.json.decode(body, type=HealthStateSet)


@pytest.mark.parametrize("field", ["superficial", "aggravated"])
def test_tracker_state_set_rejects_unknown_fields(field: str) -> None:
    """Verify a tracker state body with a field other than current or stains is rejected."""
    # Given a body with a removed damage field
    body = msgspec.json.encode({field: 2})

    # When / Then decoding it fails
    with pytest.raises(msgspec.ValidationError, match=field):
        msgspec.json.decode(body, type=TrackerStateSet)
