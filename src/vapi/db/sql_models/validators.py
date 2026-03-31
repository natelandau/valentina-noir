"""Validators for Tortoise ORM JSON fields containing enum values."""

from __future__ import annotations

from vapi.constants import CharacterClass, GameVersion


def validate_character_classes(value: list[str]) -> None:
    """Validate that all items in a character_classes JSON field are valid CharacterClass values.

    Use as a Tortoise ORM field validator to catch invalid enum strings at save time,
    regardless of the code path that writes the field.

    Args:
        value: List of character class strings from the JSON field.

    Raises:
        ValueError: If any value is not a valid CharacterClass member.
    """
    valid = {e.value for e in CharacterClass}
    for item in value:
        if item not in valid:
            msg = f"Invalid character class: {item}"
            raise ValueError(msg)


def validate_game_versions(value: list[str]) -> None:
    """Validate that all items in a game_versions JSON field are valid GameVersion values.

    Use as a Tortoise ORM field validator to catch invalid enum strings at save time,
    regardless of the code path that writes the field.

    Args:
        value: List of game version strings from the JSON field.

    Raises:
        ValueError: If any value is not a valid GameVersion member.
    """
    valid = {e.value for e in GameVersion}
    for item in value:
        if item not in valid:
            msg = f"Invalid game version: {item}"
            raise ValueError(msg)
