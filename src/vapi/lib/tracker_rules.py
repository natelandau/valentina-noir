"""Pure game rules for in-play trackers and character health.

No database access: services load state, call these functions, and persist the result.

Valentina simplifies the published rules: damage has no types, and Willpower and Humanity
are spend/gain counters. Only V5 vampires track Humanity stains.
"""

from vapi.constants import (
    CharacterClass,
    GameVersion,
    TrackerAction,
    TrackerType,
)
from vapi.lib.exceptions import ValidationError

V5_HEALTH_BASE = 3
V4_HEALTH_BASE = 7
HUMANITY_BOXES = 10

V4_HEALTH_LEVELS: tuple[str, ...] = (
    "Bruised",
    "Hurt",
    "Injured",
    "Wounded",
    "Mauled",
    "Crippled",
    "Incapacitated",
)


def health_size(*, game_version: GameVersion, stamina: int, extra_levels: int) -> int:
    """Return the number of health boxes for a character.

    V5 health is Stamina plus three; V4 has seven named levels. Both add extra levels.
    """
    if game_version == GameVersion.V5:
        return stamina + V5_HEALTH_BASE + extra_levels
    return V4_HEALTH_BASE + extra_levels


def resolve_tracker_type(
    *,
    tracker_type_v4: TrackerType | None,
    tracker_type_v5: TrackerType | None,
    game_version: GameVersion,
    character_class: CharacterClass,
) -> TrackerType | None:
    """Return the tracker a character gets for a trait's configured tracker types.

    The game version picks the configured type. Stains are a vampire rule, so every
    other class tracks Humanity as a counter.
    """
    tracker_type = tracker_type_v4 if game_version == GameVersion.V4 else tracker_type_v5
    if tracker_type == TrackerType.STAINS and character_class != CharacterClass.VAMPIRE:
        return TrackerType.COUNTER
    return tracker_type


_COUNTER_ACTIONS = (TrackerAction.SPEND, TrackerAction.GAIN, TrackerAction.RESET)
_HEALTH_ACTIONS = (TrackerAction.DAMAGE, TrackerAction.HEAL, TrackerAction.RESET)

# Actions each tracker accepts, by game version and tracker type. `DAMAGE` is health.
TRACKER_RULES: dict[GameVersion, dict[TrackerType, tuple[TrackerAction, ...]]] = {
    GameVersion.V4: {
        TrackerType.COUNTER: _COUNTER_ACTIONS,
        TrackerType.DAMAGE: _HEALTH_ACTIONS,
    },
    GameVersion.V5: {
        TrackerType.COUNTER: _COUNTER_ACTIONS,
        TrackerType.STAINS: (
            TrackerAction.ADD_STAIN,
            TrackerAction.REMOVE_STAIN,
            TrackerAction.RESET,
        ),
        TrackerType.DAMAGE: _HEALTH_ACTIONS,
    },
}


# Game version to tracker type to `actions` string list.
TrackerRulesMap = dict[str, dict[str, dict[str, list[str]]]]


def tracker_rules_for_options() -> TrackerRulesMap:
    """Return `TRACKER_RULES` as plain strings so clients can pick the controls to show."""
    return {
        version.value: {
            key: {"actions": [action.value for action in actions]} for key, actions in rules.items()
        }
        for version, rules in TRACKER_RULES.items()
    }


def validate_action(
    *, game_version: GameVersion, tracker_type: TrackerType, action: TrackerAction
) -> None:
    """Validate an action against the rules for a tracker and game version.

    Raises:
        ValidationError: If the tracker or action is not accepted.
    """
    actions = TRACKER_RULES[game_version].get(tracker_type)
    if actions is None:
        msg = f"Tracker {tracker_type.value} is not available for {game_version.value}."
        raise ValidationError(detail=msg, invalid_parameters=[{"field": "action", "message": msg}])

    if action not in actions:
        accepted = ", ".join(a.value for a in actions)
        msg = f"Action {action.value} is not accepted. Accepted actions: {accepted}."
        raise ValidationError(detail=msg, invalid_parameters=[{"field": "action", "message": msg}])


def apply_counter(*, spent: int, size: int, action: TrackerAction, amount: int) -> int:
    """Return the new spent value after a counter action.

    Raises:
        ValidationError: If spending more than the remaining current value.
        ValueError: If the action is not a counter action.
    """
    if action == TrackerAction.SPEND:
        if amount > size - spent:
            msg = f"Cannot spend {amount}: only {size - spent} remaining."
            raise ValidationError(
                detail=msg, invalid_parameters=[{"field": "amount", "message": msg}]
            )
        return spent + amount
    if action == TrackerAction.GAIN:
        return max(0, spent - amount)
    if action == TrackerAction.RESET:
        return 0
    msg = f"Unsupported counter action: {action.value}"
    raise ValueError(msg)


def apply_damage(*, damage: int, size: int, action: TrackerAction, amount: int) -> int:
    """Return the new damage after a damage, heal, or reset action.

    Damage past a full track and healing past zero are dropped.

    Raises:
        ValueError: If the action is not a health action.
    """
    if action == TrackerAction.DAMAGE:
        return min(size, damage + amount)
    if action == TrackerAction.HEAL:
        return max(0, damage - amount)
    if action == TrackerAction.RESET:
        return 0
    msg = f"Unsupported health action: {action.value}"
    raise ValueError(msg)


def apply_stains(*, stains: int, action: TrackerAction, amount: int) -> int:
    """Return the new stains after a stains action, kept within the Humanity track.

    Raises:
        ValueError: If the action is not a stains action.
    """
    if action == TrackerAction.ADD_STAIN:
        return min(HUMANITY_BOXES, stains + amount)
    if action == TrackerAction.REMOVE_STAIN:
        return max(0, stains - amount)
    if action == TrackerAction.RESET:
        return 0
    msg = f"Unsupported stains action: {action.value}"
    raise ValueError(msg)


def v4_levels(*, damage: int, extra_levels: int) -> list[tuple[str, bool]]:
    """Return V4 health levels as `(name, marked)` rows, marked from the top."""
    names = [V4_HEALTH_LEVELS[0]] * extra_levels + list(V4_HEALTH_LEVELS)
    return [(name, i < damage) for i, name in enumerate(names)]
