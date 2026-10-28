"""Test the pure tracker rules engine."""

import pytest

from vapi.constants import CharacterClass, GameVersion, TrackerAction, TrackerType
from vapi.lib.exceptions import ValidationError
from vapi.lib.tracker_rules import (
    apply_counter,
    apply_damage,
    apply_stains,
    health_size,
    resolve_tracker_type,
    tracker_rules_for_options,
    v4_levels,
    validate_action,
)


def test_spend_more_than_current_raises() -> None:
    """Verify spending more than the remaining current value is rejected."""
    # Given a counter with 1 remaining
    # When / Then spending 2 raises
    with pytest.raises(ValidationError):
        apply_counter(spent=4, size=5, action=TrackerAction.SPEND, amount=2)


def test_gain_clamps_to_size() -> None:
    """Verify gaining beyond size clamps."""
    # Given / When
    result = apply_counter(spent=1, size=5, action=TrackerAction.GAIN, amount=3)

    # Then
    assert result == 0


def test_counter_reset() -> None:
    """Verify reset restores the counter."""
    # Given / When
    result = apply_counter(spent=3, size=5, action=TrackerAction.RESET, amount=1)

    # Then
    assert result == 0


def test_apply_counter_rejects_non_counter_action() -> None:
    """Verify a counter refuses an action it does not support."""
    # Given / When / Then
    with pytest.raises(ValueError, match="damage"):
        apply_counter(spent=0, size=5, action=TrackerAction.DAMAGE, amount=1)


@pytest.mark.parametrize(
    ("damage", "action", "amount", "expected"),
    [
        (2, TrackerAction.DAMAGE, 3, 5),
        (5, TrackerAction.DAMAGE, 2, 6),
        (6, TrackerAction.DAMAGE, 1, 6),
        (4, TrackerAction.HEAL, 1, 3),
        (1, TrackerAction.HEAL, 5, 0),
        (4, TrackerAction.RESET, 1, 0),
    ],
)
def test_apply_damage(damage: int, action: TrackerAction, amount: int, expected: int) -> None:
    """Verify damage fills up to the track size and healing stops at zero."""
    # Given / When
    result = apply_damage(damage=damage, size=6, action=action, amount=amount)

    # Then
    assert result == expected


def test_apply_damage_rejects_non_health_action() -> None:
    """Verify health refuses an action it does not support."""
    # Given / When / Then
    with pytest.raises(ValueError, match="spend"):
        apply_damage(damage=0, size=6, action=TrackerAction.SPEND, amount=1)


@pytest.mark.parametrize(
    ("stains", "action", "amount", "expected"),
    [
        (2, TrackerAction.ADD_STAIN, 3, 5),
        (8, TrackerAction.ADD_STAIN, 5, 10),
        (2, TrackerAction.REMOVE_STAIN, 5, 0),
        (4, TrackerAction.RESET, 1, 0),
    ],
)
def test_apply_stains(stains: int, action: TrackerAction, amount: int, expected: int) -> None:
    """Verify stains stay between zero and the ten Humanity boxes."""
    # Given / When
    result = apply_stains(stains=stains, action=action, amount=amount)

    # Then
    assert result == expected


def test_apply_stains_rejects_non_stain_action() -> None:
    """Verify stains refuse an action they do not support."""
    # Given / When / Then
    with pytest.raises(ValueError, match="spend"):
        apply_stains(stains=0, action=TrackerAction.SPEND, amount=1)


@pytest.mark.parametrize(
    ("game_version", "stamina", "extra_levels", "expected"),
    [
        (GameVersion.V5, 3, 0, 6),
        (GameVersion.V5, 2, 1, 6),
        (GameVersion.V4, 4, 0, 7),
        (GameVersion.V4, 4, 2, 9),
    ],
)
def test_health_size(
    game_version: GameVersion, stamina: int, extra_levels: int, expected: int
) -> None:
    """Verify V5 health follows Stamina and V4 health ignores it."""
    # Given / When
    result = health_size(game_version=game_version, stamina=stamina, extra_levels=extra_levels)

    # Then
    assert result == expected


@pytest.mark.parametrize("character_class", list(CharacterClass))
def test_resolve_tracker_type_stains_only_for_vampires(character_class: CharacterClass) -> None:
    """Verify V5 stains stay stains for vampires and become a counter for every other class."""
    # Given / When
    result = resolve_tracker_type(
        tracker_type_v4=TrackerType.COUNTER,
        tracker_type_v5=TrackerType.STAINS,
        game_version=GameVersion.V5,
        character_class=character_class,
    )

    # Then
    expected = (
        TrackerType.STAINS if character_class == CharacterClass.VAMPIRE else TrackerType.COUNTER
    )
    assert result == expected


@pytest.mark.parametrize(
    ("game_version", "expected"),
    [(GameVersion.V4, TrackerType.COUNTER), (GameVersion.V5, None)],
)
def test_resolve_tracker_type_picks_by_game_version(
    game_version: GameVersion, expected: TrackerType | None
) -> None:
    """Verify the game version picks the configured type and other types ignore the class."""
    # Given / When
    result = resolve_tracker_type(
        tracker_type_v4=TrackerType.COUNTER,
        tracker_type_v5=None,
        game_version=game_version,
        character_class=CharacterClass.MORTAL,
    )

    # Then
    assert result == expected


def test_v4_levels_mark_from_the_top() -> None:
    """Verify V4 levels are marked from Bruised down and extra levels add Bruised rows."""
    # Given / When
    levels = v4_levels(damage=2, extra_levels=1)

    # Then
    assert levels == [
        ("Bruised", True),
        ("Bruised", True),
        ("Hurt", False),
        ("Injured", False),
        ("Wounded", False),
        ("Mauled", False),
        ("Crippled", False),
        ("Incapacitated", False),
    ]


def test_validate_action_rejects_action_for_type() -> None:
    """Verify an action outside a tracker's rule is rejected."""
    # Given / When / Then
    with pytest.raises(ValidationError, match="spend"):
        validate_action(
            game_version=GameVersion.V5, tracker_type=TrackerType.DAMAGE, action=TrackerAction.SPEND
        )


def test_validate_action_rejects_stains_in_v4() -> None:
    """Verify V4 has no stains tracker."""
    # Given / When / Then
    with pytest.raises(ValidationError, match="STAINS"):
        validate_action(
            game_version=GameVersion.V4,
            tracker_type=TrackerType.STAINS,
            action=TrackerAction.ADD_STAIN,
        )


def test_tracker_rules_for_options_returns_plain_strings() -> None:
    """Verify the options map mirrors TRACKER_RULES as plain strings."""
    # Given the tracker rules constant
    # When building the options map
    rules = tracker_rules_for_options()

    # Then values are plain action lists keyed by version and tracker
    assert rules == {
        "V4": {
            "COUNTER": {"actions": ["spend", "gain", "reset"]},
            "DAMAGE": {"actions": ["damage", "heal", "reset"]},
        },
        "V5": {
            "COUNTER": {"actions": ["spend", "gain", "reset"]},
            "STAINS": {"actions": ["add_stain", "remove_stain", "reset"]},
            "DAMAGE": {"actions": ["damage", "heal", "reset"]},
        },
    }
