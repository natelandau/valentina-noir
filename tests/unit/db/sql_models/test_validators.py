"""Unit tests for JSON field enum validators."""

from __future__ import annotations

import pytest

from vapi.db.sql_models.validators import validate_character_classes, validate_game_versions


class TestValidateCharacterClasses:
    """Tests for character_classes JSON field validator."""

    def test_valid_character_classes(self) -> None:
        """Verify valid character class values pass validation."""
        # Given valid character class values
        value = ["VAMPIRE", "WEREWOLF", "MAGE"]

        # When validating
        # Then no exception is raised
        validate_character_classes(value)

    def test_invalid_character_class_raises(self) -> None:
        """Verify invalid character class value raises ValueError."""
        # Given an invalid character class
        value = ["VAMPIRE", "INVALID_CLASS"]

        # When/Then validation raises ValueError
        with pytest.raises(ValueError, match="Invalid character class: INVALID_CLASS"):
            validate_character_classes(value)

    def test_empty_list_passes(self) -> None:
        """Verify empty list passes validation."""
        validate_character_classes([])


class TestValidateGameVersions:
    """Tests for game_versions JSON field validator."""

    def test_valid_game_versions(self) -> None:
        """Verify valid game version values pass validation."""
        # Given valid game version values
        value = ["V4", "V5"]

        # When validating
        # Then no exception is raised
        validate_game_versions(value)

    def test_invalid_game_version_raises(self) -> None:
        """Verify invalid game version value raises ValueError."""
        # Given an invalid game version
        value = ["V4", "V99"]

        # When/Then validation raises ValueError
        with pytest.raises(ValueError, match="Invalid game version: V99"):
            validate_game_versions(value)

    def test_empty_list_passes(self) -> None:
        """Verify empty list passes validation."""
        validate_game_versions([])
