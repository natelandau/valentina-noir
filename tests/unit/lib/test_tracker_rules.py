"""Test the pure tracker rules engine."""

import pytest

from vapi.constants import DamageType, GameVersion, TrackerAction
from vapi.lib.exceptions import ValidationError
from vapi.lib.tracker_rules import (
    HEALTH_RULE_KEY,
    DamageMarks,
    apply_counter,
    apply_damage,
    apply_stains,
    clamp_marks,
    damage_track_fields,
    health_size,
    render_boxes,
    tracker_rules_for_options,
    v4_levels,
    v4_penalty_from_levels,
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


def test_v5_superficial_overflow_becomes_aggravated() -> None:
    """Verify V5 superficial overflow converts superficial to aggravated."""
    # Given
    marks = DamageMarks(superficial=5)

    # When
    result = apply_damage(
        marks=marks,
        size=5,
        game_version=GameVersion.V5,
        action=TrackerAction.DAMAGE,
        amount=2,
        damage_type=DamageType.SUPERFICIAL,
    )

    # Then
    assert result == DamageMarks(superficial=3, aggravated=2)


def test_v5_aggravated_fills_empty_then_converts() -> None:
    """Verify V5 aggravated fills empty boxes then converts superficial."""
    # Given
    marks = DamageMarks(superficial=3)

    # When
    result = apply_damage(
        marks=marks,
        size=4,
        game_version=GameVersion.V5,
        action=TrackerAction.DAMAGE,
        amount=2,
        damage_type=DamageType.AGGRAVATED,
    )

    # Then
    assert result == DamageMarks(superficial=2, aggravated=2)


def test_v5_aggravated_stops_when_all_aggravated() -> None:
    """Verify further aggravated damage is ignored on a full aggravated track."""
    # Given
    marks = DamageMarks(aggravated=3)

    # When
    result = apply_damage(
        marks=marks,
        size=3,
        game_version=GameVersion.V5,
        action=TrackerAction.DAMAGE,
        amount=1,
        damage_type=DamageType.AGGRAVATED,
    )

    # Then
    assert result == DamageMarks(aggravated=3)


def test_v4_bashing_overflow_upgrades_to_lethal() -> None:
    """Verify V4 bashing overflow upgrades bashing to lethal."""
    # Given
    marks = DamageMarks(bashing=7)

    # When
    result = apply_damage(
        marks=marks,
        size=7,
        game_version=GameVersion.V4,
        action=TrackerAction.DAMAGE,
        amount=1,
        damage_type=DamageType.BASHING,
    )

    # Then
    assert result == DamageMarks(bashing=6, lethal=1)


def test_v4_lethal_overflow_upgrades_least_severe() -> None:
    """Verify V4 lethal overflow upgrades the least severe box one step."""
    # Given
    marks = DamageMarks(lethal=7)

    # When
    result = apply_damage(
        marks=marks,
        size=7,
        game_version=GameVersion.V4,
        action=TrackerAction.DAMAGE,
        amount=1,
        damage_type=DamageType.LETHAL,
    )

    # Then
    assert result == DamageMarks(lethal=6, aggravated=1)


def test_heal_more_than_marked_clamps() -> None:
    """Verify healing more than is marked clamps at zero."""
    # Given
    marks = DamageMarks(superficial=1)

    # When
    result = apply_damage(
        marks=marks,
        size=5,
        game_version=GameVersion.V5,
        action=TrackerAction.HEAL,
        amount=3,
        damage_type=DamageType.SUPERFICIAL,
    )

    # Then
    assert result == DamageMarks()


def test_damage_reset_clears_all_marks() -> None:
    """Verify reset clears every mark."""
    # Given
    marks = DamageMarks(superficial=1, aggravated=2)

    # When
    result = apply_damage(
        marks=marks,
        size=5,
        game_version=GameVersion.V5,
        action=TrackerAction.RESET,
        amount=1,
        damage_type=None,
    )

    # Then
    assert result == DamageMarks()


def test_stains_overflow_reports_willpower_damage() -> None:
    """Verify stains beyond capacity report willpower damage."""
    # Given / When
    result = apply_stains(stains=2, humanity=7, action=TrackerAction.ADD_STAIN, amount=3)

    # Then
    assert result == (5, 2)


def test_stains_stored_max_ten() -> None:
    """Verify stored stains never exceed ten."""
    # Given / When
    result = apply_stains(stains=9, humanity=0, action=TrackerAction.ADD_STAIN, amount=4)

    # Then
    assert result[0] == 10


def test_remove_stain_clamps_at_zero() -> None:
    """Verify removing stains clamps at zero with no willpower damage."""
    # Given / When
    result = apply_stains(stains=1, humanity=5, action=TrackerAction.REMOVE_STAIN, amount=3)

    # Then
    assert result == (0, 0)


def test_clamp_trims_least_severe_first() -> None:
    """Verify clamping removes the least severe marks first."""
    # Given
    marks = DamageMarks(superficial=2, aggravated=2)

    # When
    result = clamp_marks(marks=marks, size=3)

    # Then
    assert result == DamageMarks(superficial=1, aggravated=2)


def test_render_boxes_order() -> None:
    """Verify boxes render most severe first, then empty."""
    # Given
    marks = DamageMarks(aggravated=1, superficial=2)

    # When
    result = render_boxes(marks=marks, size=5)

    # Then
    assert result == [
        DamageType.AGGRAVATED,
        DamageType.SUPERFICIAL,
        DamageType.SUPERFICIAL,
        None,
        None,
    ]


def test_v4_levels_extra_bruised() -> None:
    """Verify extra levels add Bruised rows at the top."""
    # Given / When
    result = v4_levels(marks=DamageMarks(), extra_levels=1)

    # Then
    assert len(result) == 8
    assert [row[0] for row in result[:2]] == ["Bruised", "Bruised"]


@pytest.mark.parametrize(
    ("marks", "expected"),
    [(DamageMarks(bashing=4), -2), (DamageMarks(bashing=7), None), (DamageMarks(), 0)],
)
def test_v4_penalty_from_levels(marks: DamageMarks, expected: int | None) -> None:
    """Verify the penalty follows the deepest marked level."""
    # Given V4 levels with the marks
    levels = v4_levels(marks=marks, extra_levels=0)

    # When reading the penalty
    result = v4_penalty_from_levels(levels)

    # Then it matches the deepest marked level
    assert result == expected


def test_validate_action_rejects_wrong_damage_type() -> None:
    """Verify an unsupported damage type is rejected and the accepted ones are named."""
    # Given / When / Then
    with pytest.raises(ValidationError) as exc_info:
        validate_action(
            game_version=GameVersion.V4,
            rule_key=HEALTH_RULE_KEY,
            action=TrackerAction.DAMAGE,
            damage_type=DamageType.SUPERFICIAL,
        )

    assert "invalid" in str(exc_info.value.detail)
    assert "BASHING" in str(exc_info.value.detail)


def test_validate_action_rejects_action_for_type() -> None:
    """Verify an unsupported action is rejected."""
    # Given / When / Then
    with pytest.raises(ValidationError):
        validate_action(
            game_version=GameVersion.V4,
            rule_key="COUNTER",
            action=TrackerAction.DAMAGE,
            damage_type=None,
        )


def test_validate_action_requires_damage_type_for_damage() -> None:
    """Verify damage needs a damage type."""
    # Given / When / Then
    with pytest.raises(ValidationError):
        validate_action(
            game_version=GameVersion.V5,
            rule_key="DAMAGE",
            action=TrackerAction.DAMAGE,
            damage_type=None,
        )


def test_validate_action_rejects_damage_type_on_reset() -> None:
    """Verify a damage type is rejected for actions that take none."""
    # Given / When / Then
    with pytest.raises(ValidationError):
        validate_action(
            game_version=GameVersion.V5,
            rule_key="DAMAGE",
            action=TrackerAction.RESET,
            damage_type=DamageType.SUPERFICIAL,
        )


def test_validate_action_missing_damage_type_says_required() -> None:
    """Verify the missing case reads as required."""
    # Given / When / Then
    with pytest.raises(ValidationError) as exc_info:
        validate_action(
            game_version=GameVersion.V5,
            rule_key="DAMAGE",
            action=TrackerAction.HEAL,
            damage_type=None,
        )

    assert "required" in str(exc_info.value.detail)


def test_apply_counter_rejects_non_counter_action() -> None:
    """Verify an unexpected action raises instead of resetting."""
    # Given / When / Then
    with pytest.raises(ValueError, match="Unsupported"):
        apply_counter(spent=1, size=5, action=TrackerAction.DAMAGE, amount=1)


def test_apply_stains_rejects_non_stain_action() -> None:
    """Verify an unexpected action raises instead of resetting."""
    # Given / When / Then
    with pytest.raises(ValueError, match="Unsupported"):
        apply_stains(stains=1, humanity=5, action=TrackerAction.SPEND, amount=1)


def test_apply_damage_requires_damage_type() -> None:
    """Verify damage without a damage type raises."""
    # Given / When / Then
    with pytest.raises(ValueError, match="required"):
        apply_damage(
            marks=DamageMarks(),
            size=5,
            game_version=GameVersion.V5,
            action=TrackerAction.DAMAGE,
            amount=1,
            damage_type=None,
        )


@pytest.mark.parametrize(("bashing", "expected"), [(7, -5), (8, None)])
def test_v4_penalty_from_levels_with_extra_levels(bashing: int, expected: int | None) -> None:
    """Verify extra levels shift the incapacitated threshold."""
    # Given V4 levels with one extra Bruised level
    levels = v4_levels(marks=DamageMarks(bashing=bashing), extra_levels=1)

    # When reading the penalty
    result = v4_penalty_from_levels(levels)

    # Then the threshold moves down one level
    assert result == expected


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


@pytest.mark.parametrize(
    ("marks", "size", "impaired"),
    [
        (DamageMarks(superficial=2, aggravated=1), 3, True),
        (DamageMarks(superficial=1), 3, False),
        (DamageMarks(), 0, False),
    ],
)
def test_damage_track_fields(marks: DamageMarks, size: int, impaired: bool) -> None:
    """Verify the boxes fill the track and impairment needs every box marked."""
    # Given / When
    boxes, is_impaired = damage_track_fields(marks=marks, size=size)

    # Then
    assert len(boxes) == size
    assert is_impaired is impaired


def test_v4_lethal_on_full_track_upgrades_bashing() -> None:
    """Verify lethal overflow upgrades a bashing box first."""
    # Given
    marks = DamageMarks(bashing=2, lethal=5)

    # When
    result = apply_damage(
        marks=marks,
        size=7,
        game_version=GameVersion.V4,
        action=TrackerAction.DAMAGE,
        amount=1,
        damage_type=DamageType.LETHAL,
    )

    # Then
    assert result == DamageMarks(bashing=1, lethal=6)


def test_v4_aggravated_overflow_converts_least_severe() -> None:
    """Verify aggravated overflow converts bashing, then lethal."""
    # Given
    marks = DamageMarks(bashing=1, lethal=6)

    # When
    result = apply_damage(
        marks=marks,
        size=7,
        game_version=GameVersion.V4,
        action=TrackerAction.DAMAGE,
        amount=2,
        damage_type=DamageType.AGGRAVATED,
    )

    # Then
    assert result == DamageMarks(lethal=5, aggravated=2)


def test_stains_already_over_capacity_only_new_stains_overflow() -> None:
    """Verify stains already beyond capacity do not report prior overflow again."""
    # Given / When
    result = apply_stains(stains=6, humanity=7, action=TrackerAction.ADD_STAIN, amount=2)

    # Then
    assert result == (8, 2)


def test_tracker_rules_for_options_returns_plain_strings() -> None:
    """Verify the options map mirrors TRACKER_RULES as plain strings."""
    # Given the tracker rules constant
    # When building the options map
    rules = tracker_rules_for_options()

    # Then values are plain strings keyed by version and tracker
    assert rules["V4"]["COUNTER"] == {"actions": ["spend", "gain", "reset"], "damage_types": []}
    assert rules["V4"][HEALTH_RULE_KEY]["damage_types"] == ["BASHING", "LETHAL", "AGGRAVATED"]
    assert rules["V5"]["DAMAGE"]["damage_types"] == ["SUPERFICIAL", "AGGRAVATED"]
    assert rules["V5"]["STAINS"]["actions"] == ["add_stain", "remove_stain", "reset"]
