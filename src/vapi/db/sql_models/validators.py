"""Validators for Tortoise ORM JSON fields containing enum values."""

from __future__ import annotations

import re

from tortoise.exceptions import ValidationError

from vapi.constants import CharacterClass, GameVersion

NUM_CHOICES_MAX: int = 10
NUM_CHOICES_MIN: int = 1
STARTING_POINTS_MAX: int = 100
STARTING_POINTS_MIN: int = 0
_VALID_CHARACTER_CLASSES: frozenset[str] = frozenset(e.value for e in CharacterClass)
_VALID_GAME_VERSIONS: frozenset[str] = frozenset(e.value for e in GameVersion)
XP_COST_MAX: int = 100
XP_COST_MIN: int = 0


def _validate_enum_list(value: list[str], valid: frozenset[str], label: str) -> None:
    """Validate that all items in a JSON list field are valid enum values.

    Args:
        value: List of strings from the JSON field.
        valid: Set of valid enum string values.
        label: Human-readable label for error messages.

    Raises:
        ValidationError: If any value is not in the valid set.
    """
    for item in value:
        if item not in valid:
            msg = f"Invalid {label}: {item}"
            raise ValidationError(msg)


def validate_character_classes(value: list[str]) -> None:
    """Validate that all items are valid CharacterClass values.

    Use as a Tortoise ORM field validator to catch invalid enum strings at save time,
    regardless of the code path that writes the field.

    Args:
        value: List of character class strings from the JSON field.

    Raises:
        ValidationError: If any value is not a valid CharacterClass member.
    """
    _validate_enum_list(value, _VALID_CHARACTER_CLASSES, "character class")


def validate_game_versions(value: list[str]) -> None:
    """Validate that all items are valid GameVersion values.

    Use as a Tortoise ORM field validator to catch invalid enum strings at save time,
    regardless of the code path that writes the field.

    Args:
        value: List of game version strings from the JSON field.

    Raises:
        ValidationError: If any value is not a valid GameVersion member.
    """
    _validate_enum_list(value, _VALID_GAME_VERSIONS, "game version")


def _validate_int_range(*, value: int, minimum: int, maximum: int, field: str) -> None:
    """Raise when an integer field is outside its inclusive range.

    Args:
        value: The integer to validate.
        minimum: The smallest allowed value.
        maximum: The largest allowed value.
        field: The field name to report in the error message.

    Raises:
        ValidationError: If value is outside the range.
    """
    if not (minimum <= value <= maximum):
        msg = f"{field} must be between {minimum} and {maximum}, got {value}"
        raise ValidationError(msg)


def validate_company_settings_starting_points(value: int) -> None:
    """Validate that character_autogen_starting_points is within the allowed range of 0-100.

    Use as a Tortoise ORM field validator to enforce business rules on starting points
    at save time, regardless of the code path that writes the field.

    Args:
        value: The starting points integer to validate.

    Raises:
        ValidationError: If value is outside the range 0-100.
    """
    _validate_int_range(
        value=value,
        minimum=STARTING_POINTS_MIN,
        maximum=STARTING_POINTS_MAX,
        field="character_autogen_starting_points",
    )


def validate_company_settings_custom_flaw_xp_cost(value: int) -> None:
    """Validate that custom_flaw_xp_cost is within the allowed range of 0-100.

    Use as a Tortoise ORM field validator so every write path enforces the range.

    Args:
        value: The XP cost integer to validate.

    Raises:
        ValidationError: If value is outside the range 0-100.
    """
    _validate_int_range(
        value=value, minimum=XP_COST_MIN, maximum=XP_COST_MAX, field="custom_flaw_xp_cost"
    )


def validate_company_settings_xp_cost(value: int) -> None:
    """Validate that character_autogen_xp_cost is within the allowed range of 0-100.

    Use as a Tortoise ORM field validator to enforce business rules on XP cost
    at save time, regardless of the code path that writes the field.

    Args:
        value: The XP cost integer to validate.

    Raises:
        ValidationError: If value is outside the range 0-100.
    """
    _validate_int_range(
        value=value, minimum=XP_COST_MIN, maximum=XP_COST_MAX, field="character_autogen_xp_cost"
    )


def validate_company_settings_num_choices(value: int) -> None:
    """Validate that character_autogen_num_choices is within the allowed range of 1-10.

    Use as a Tortoise ORM field validator to enforce business rules on the number
    of autogen choices at save time, regardless of the code path that writes the field.

    Args:
        value: The number of choices integer to validate.

    Raises:
        ValidationError: If value is outside the range 1-10.
    """
    _validate_int_range(
        value=value,
        minimum=NUM_CHOICES_MIN,
        maximum=NUM_CHOICES_MAX,
        field="character_autogen_num_choices",
    )


EMAIL_PATTERN: str = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
_EMAIL_RE = re.compile(EMAIL_PATTERN)


def validate_email_format(value: str) -> None:
    """Validate that a string looks like an email address.

    Check for the presence of exactly one @ with non-empty local and domain parts,
    where the domain contains at least one dot. This matches the level of validation
    that Pydantic's EmailStr provided in the old Beanie models.

    Args:
        value: The email string to validate.

    Raises:
        ValidationError: If the value does not match basic email format.
    """
    if not _EMAIL_RE.match(value):
        msg = f"Invalid email format: {value}"
        raise ValidationError(msg)
