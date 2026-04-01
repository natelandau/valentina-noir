"""Unit tests for JSON field enum validators."""

from __future__ import annotations

import pytest
from tortoise.exceptions import ValidationError as TortoiseValidationError

from vapi.db.sql_models.validators import (
    validate_character_classes,
    validate_company_settings_num_choices,
    validate_company_settings_xp_cost,
    validate_game_versions,
)


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
        with pytest.raises(TortoiseValidationError, match="Invalid character class: INVALID_CLASS"):
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
        with pytest.raises(TortoiseValidationError, match="Invalid game version: V99"):
            validate_game_versions(value)

    def test_empty_list_passes(self) -> None:
        """Verify empty list passes validation."""
        validate_game_versions([])


class TestCompanySettingsValidators:
    """Tests for CompanySettings integer field validators."""

    @pytest.mark.parametrize("value", [0, 1, 50, 100])
    def test_validate_xp_cost_valid(self, value: int) -> None:
        """Verify valid xp cost values pass validation."""
        # When validating a valid value
        # Then no exception is raised
        validate_company_settings_xp_cost(value)

    @pytest.mark.parametrize("value", [-1, 101, 999])
    def test_validate_xp_cost_invalid(self, value: int) -> None:
        """Verify out-of-range xp cost values raise ValueError."""
        # When/Then validation raises ValueError referencing the field name
        with pytest.raises(TortoiseValidationError, match="character_autogen_xp_cost"):
            validate_company_settings_xp_cost(value)

    @pytest.mark.parametrize("value", [1, 5, 10])
    def test_validate_num_choices_valid(self, value: int) -> None:
        """Verify valid num choices values pass validation."""
        # When validating a valid value
        # Then no exception is raised
        validate_company_settings_num_choices(value)

    @pytest.mark.parametrize("value", [0, -1, 11, 100])
    def test_validate_num_choices_invalid(self, value: int) -> None:
        """Verify out-of-range num choices values raise ValueError."""
        # When/Then validation raises ValueError referencing the field name
        with pytest.raises(TortoiseValidationError, match="character_autogen_num_choices"):
            validate_company_settings_num_choices(value)
