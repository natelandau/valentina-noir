"""Pure game rules for in-play trackers and character health.

No database access: services load state, call these functions, and persist the result.
"""

from dataclasses import dataclass, replace

from vapi.constants import DamageType, GameVersion, TrackerAction, TrackerType
from vapi.lib.exceptions import ValidationError

HEALTH_RULE_KEY = "HEALTH"
V5_HEALTH_BASE = 3
V4_HEALTH_BASE = 7
HUMANITY_BOXES = 10

V4_HEALTH_LEVELS: tuple[tuple[str, int | None], ...] = (
    ("Bruised", 0),
    ("Hurt", -1),
    ("Injured", -1),
    ("Wounded", -2),
    ("Mauled", -2),
    ("Crippled", -5),
    ("Incapacitated", None),
)

_DAMAGE_ACTIONS = (TrackerAction.DAMAGE, TrackerAction.HEAL)


def health_size(*, game_version: GameVersion, stamina: int, extra_levels: int) -> int:
    """Return the number of health boxes for a character.

    V5 health is Stamina plus three; V4 has seven named levels. Both add extra levels.
    """
    if game_version == GameVersion.V5:
        return stamina + V5_HEALTH_BASE + extra_levels
    return V4_HEALTH_BASE + extra_levels


@dataclass(frozen=True)
class TrackerRule:
    """Actions and damage types a tracker accepts for one game version."""

    actions: tuple[TrackerAction, ...]
    damage_types: tuple[DamageType, ...]


_V5_DAMAGE_RULE = TrackerRule(
    actions=(TrackerAction.DAMAGE, TrackerAction.HEAL, TrackerAction.RESET),
    damage_types=(DamageType.SUPERFICIAL, DamageType.AGGRAVATED),
)

TRACKER_RULES: dict[GameVersion, dict[str, TrackerRule]] = {
    GameVersion.V4: {
        TrackerType.COUNTER.value: TrackerRule(
            actions=(TrackerAction.SPEND, TrackerAction.GAIN, TrackerAction.RESET),
            damage_types=(),
        ),
        HEALTH_RULE_KEY: TrackerRule(
            actions=(TrackerAction.DAMAGE, TrackerAction.HEAL, TrackerAction.RESET),
            damage_types=(DamageType.BASHING, DamageType.LETHAL, DamageType.AGGRAVATED),
        ),
    },
    GameVersion.V5: {
        TrackerType.DAMAGE.value: _V5_DAMAGE_RULE,
        HEALTH_RULE_KEY: _V5_DAMAGE_RULE,
        TrackerType.STAINS.value: TrackerRule(
            actions=(TrackerAction.ADD_STAIN, TrackerAction.REMOVE_STAIN, TrackerAction.RESET),
            damage_types=(),
        ),
    },
}


# Game version to tracker key to `actions` and `damage_types` string lists.
TrackerRulesMap = dict[str, dict[str, dict[str, list[str]]]]


def tracker_rules_for_options() -> TrackerRulesMap:
    """Return `TRACKER_RULES` as plain strings so clients can pick the controls to show."""
    return {
        version.value: {
            key: {
                "actions": [action.value for action in rule.actions],
                "damage_types": [damage.value for damage in rule.damage_types],
            }
            for key, rule in rules.items()
        }
        for version, rules in TRACKER_RULES.items()
    }


@dataclass(frozen=True)
class DamageMarks:
    """Marked boxes on a damage track, by type."""

    bashing: int = 0
    lethal: int = 0
    superficial: int = 0
    aggravated: int = 0

    @property
    def total(self) -> int:
        """Return the number of marked boxes."""
        return self.bashing + self.lethal + self.superficial + self.aggravated


def _names(values: tuple[DamageType, ...] | tuple[TrackerAction, ...]) -> str:
    return ", ".join(v.value for v in values)


def validate_action(
    *,
    game_version: GameVersion,
    rule_key: str,
    action: TrackerAction,
    damage_type: DamageType | None,
) -> None:
    """Validate an action and damage type against the rules for a game version.

    Raises:
        ValidationError: If the tracker, action, or damage type is not accepted.
    """
    rule = TRACKER_RULES[game_version].get(rule_key)
    if rule is None:
        msg = f"Tracker {rule_key} is not available for {game_version.value}."
        raise ValidationError(detail=msg, invalid_parameters=[{"field": "action", "message": msg}])

    if action not in rule.actions:
        msg = f"Action {action.value} is not accepted. Accepted actions: {_names(rule.actions)}."
        raise ValidationError(detail=msg, invalid_parameters=[{"field": "action", "message": msg}])

    if action in _DAMAGE_ACTIONS:
        if damage_type is None:
            msg = f"damage_type is required for {action.value}. Accepted damage types: {_names(rule.damage_types)}."
            raise ValidationError(
                detail=msg, invalid_parameters=[{"field": "damage_type", "message": msg}]
            )
        if damage_type not in rule.damage_types:
            msg = f"damage_type {damage_type.value} is invalid. Accepted damage types: {_names(rule.damage_types)}."
            raise ValidationError(
                detail=msg, invalid_parameters=[{"field": "damage_type", "message": msg}]
            )
    elif damage_type is not None:
        msg = f"damage_type is not accepted for {action.value}."
        raise ValidationError(
            detail=msg, invalid_parameters=[{"field": "damage_type", "message": msg}]
        )


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


def _step_up(marks: DamageMarks) -> DamageMarks | None:
    """Upgrade the least severe V4 box one step (bashing to lethal, else lethal to aggravated)."""
    if marks.bashing > 0:
        return replace(marks, bashing=marks.bashing - 1, lethal=marks.lethal + 1)
    if marks.lethal > 0:
        return replace(marks, lethal=marks.lethal - 1, aggravated=marks.aggravated + 1)
    return None


def _convert_aggravated(marks: DamageMarks, *, game_version: GameVersion) -> DamageMarks | None:
    """Turn the least severe non-aggravated box into aggravated."""
    if game_version == GameVersion.V5:
        if marks.superficial > 0:
            return replace(
                marks, superficial=marks.superficial - 1, aggravated=marks.aggravated + 1
            )
        return None
    field = "bashing" if marks.bashing > 0 else "lethal"
    if getattr(marks, field) == 0:
        return None
    return replace(marks, **{field: getattr(marks, field) - 1, "aggravated": marks.aggravated + 1})


def apply_damage(
    *,
    marks: DamageMarks,
    size: int,
    game_version: GameVersion,
    action: TrackerAction,
    amount: int,
    damage_type: DamageType | None,
) -> DamageMarks:
    """Return the new marks after a damage, heal, or reset action.

    Healing more than is marked clamps at zero.

    Raises:
        ValueError: If a damage or heal action has no damage type.
    """
    if action == TrackerAction.RESET:
        return DamageMarks()

    if damage_type is None:
        msg = f"damage_type is required for {action.value}"
        raise ValueError(msg)

    field = damage_type.value.lower()

    if action == TrackerAction.HEAL:
        current = getattr(marks, field)
        return replace(marks, **{field: max(0, current - amount)})

    for _ in range(amount):
        if marks.total < size:
            marks = replace(marks, **{field: getattr(marks, field) + 1})
            continue

        if damage_type == DamageType.AGGRAVATED or game_version == GameVersion.V5:
            upgraded = _convert_aggravated(marks, game_version=game_version)
        else:
            upgraded = _step_up(marks)

        if upgraded is None:
            break
        marks = upgraded

    return marks


def apply_stains(
    *, stains: int, humanity: int, action: TrackerAction, amount: int
) -> tuple[int, int]:
    """Return `(new_stains, willpower_aggravated_to_apply)` after a stains action."""
    if action == TrackerAction.ADD_STAIN:
        capacity = HUMANITY_BOXES - humanity
        overflow = max(0, stains + amount - capacity) - max(0, stains - capacity)
        return min(HUMANITY_BOXES, stains + amount), overflow
    if action == TrackerAction.REMOVE_STAIN:
        return max(0, stains - amount), 0
    if action == TrackerAction.RESET:
        return 0, 0
    msg = f"Unsupported stains action: {action.value}"
    raise ValueError(msg)


def clamp_marks(*, marks: DamageMarks, size: int) -> DamageMarks:
    """Trim marks to fit the track, removing the least severe first."""
    excess = marks.total - size
    if excess <= 0:
        return marks

    values = {
        "bashing": marks.bashing,
        "lethal": marks.lethal,
        "superficial": marks.superficial,
        "aggravated": marks.aggravated,
    }
    for field in ("bashing", "lethal", "superficial", "aggravated"):
        cut = min(values[field], excess)
        values[field] -= cut
        excess -= cut
    return DamageMarks(**values)


def render_boxes(*, marks: DamageMarks, size: int) -> list[DamageType | None]:
    """Return the track as boxes, most severe first, padded with empty boxes."""
    marks = clamp_marks(marks=marks, size=size)
    boxes: list[DamageType | None] = []
    boxes.extend([DamageType.AGGRAVATED] * marks.aggravated)
    boxes.extend([DamageType.LETHAL] * marks.lethal)
    boxes.extend([DamageType.BASHING] * marks.bashing)
    boxes.extend([DamageType.SUPERFICIAL] * marks.superficial)
    boxes.extend([None] * (size - len(boxes)))
    return boxes


def damage_track_fields(*, marks: DamageMarks, size: int) -> tuple[list[DamageType | None], bool]:
    """Return a damage track's rendered boxes and whether every box is marked.

    A track with no boxes is never impaired.
    """
    boxes = render_boxes(marks=marks, size=size)
    return boxes, size > 0 and all(box is not None for box in boxes)


def v4_levels(
    *, marks: DamageMarks, extra_levels: int
) -> list[tuple[str, int | None, DamageType | None]]:
    """Return V4 health levels as `(name, penalty, damage_type)` rows."""
    names = [V4_HEALTH_LEVELS[0]] * extra_levels + list(V4_HEALTH_LEVELS)
    boxes = render_boxes(marks=marks, size=len(names))
    return [(name, penalty, box) for (name, penalty), box in zip(names, boxes, strict=True)]


def v4_penalty_from_levels(levels: list[tuple[str, int | None, DamageType | None]]) -> int | None:
    """Return the penalty of the deepest marked level from `v4_levels` rows.

    Returns `None` when incapacitated and 0 when no level is marked.
    """
    marked = sum(1 for _, _, box in levels if box is not None)
    if marked == 0:
        return 0
    return levels[marked - 1][1]
