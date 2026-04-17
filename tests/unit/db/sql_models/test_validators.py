"""Unit tests for Tortoise ORM field validators."""

from __future__ import annotations

import pytest
from tortoise.exceptions import ValidationError as TortoiseValidationError
from tortoise.validators import MaxValueValidator, MinLengthValidator, MinValueValidator

from vapi.db.sql_models.validators import (
    validate_character_classes,
    validate_company_settings_num_choices,
    validate_company_settings_starting_points,
    validate_company_settings_xp_cost,
    validate_email_format,
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

    @pytest.mark.parametrize("value", [0, 1, 50, 99, 100])
    def test_validate_starting_points_valid(self, value: int) -> None:
        """Verify valid starting points values pass validation."""
        # When validating a valid value
        # Then no exception is raised
        validate_company_settings_starting_points(value)

    @pytest.mark.parametrize("value", [-1, -100, 101, 999])
    def test_validate_starting_points_invalid(self, value: int) -> None:
        """Verify out-of-range starting points values raise ValidationError."""
        # When/Then validation raises ValidationError referencing the field name
        with pytest.raises(TortoiseValidationError, match="character_autogen_starting_points"):
            validate_company_settings_starting_points(value)

    def test_validate_starting_points_error_message_includes_value(self) -> None:
        """Verify the error message surfaces the offending value to aid debugging."""
        # Given an out-of-range value
        value = 150

        # When/Then the raised error names the offending value
        with pytest.raises(TortoiseValidationError, match="got 150"):
            validate_company_settings_starting_points(value)


class TestMinLengthValidator:
    """Tests for Tortoise built-in MinLengthValidator used on model fields."""

    @pytest.mark.parametrize("value", ["abc", "abcd", "a long valid string"])
    def test_valid_min_length_3(self, value: str) -> None:
        """Verify strings meeting min_length=3 pass validation."""
        # When validating a string that meets the minimum
        # Then no exception is raised
        MinLengthValidator(3)(value)

    @pytest.mark.parametrize("value", ["", "a", "ab"])
    def test_invalid_min_length_3(self, value: str) -> None:
        """Verify strings shorter than min_length=3 raise ValidationError."""
        # When/Then validation raises for too-short strings
        with pytest.raises(TortoiseValidationError):
            MinLengthValidator(3)(value)

    @pytest.mark.parametrize("value", ["ab", "abc", "abcd"])
    def test_valid_min_length_2(self, value: str) -> None:
        """Verify strings meeting min_length=2 pass validation."""
        MinLengthValidator(2)(value)

    @pytest.mark.parametrize("value", ["", "a"])
    def test_invalid_min_length_2(self, value: str) -> None:
        """Verify strings shorter than min_length=2 raise ValidationError."""
        with pytest.raises(TortoiseValidationError):
            MinLengthValidator(2)(value)


class TestRangeValidators:
    """Tests for Tortoise built-in MinValueValidator and MaxValueValidator."""

    @pytest.mark.parametrize("value", [0, 1, 3, 5])
    def test_valid_range_0_5(self, value: int) -> None:
        """Verify values within 0-5 pass both min and max validators."""
        MinValueValidator(0)(value)
        MaxValueValidator(5)(value)

    @pytest.mark.parametrize("value", [-1, -100])
    def test_below_min_0(self, value: int) -> None:
        """Verify values below 0 raise ValidationError."""
        with pytest.raises(TortoiseValidationError):
            MinValueValidator(0)(value)

    @pytest.mark.parametrize("value", [6, 100])
    def test_above_max_5(self, value: int) -> None:
        """Verify values above 5 raise ValidationError."""
        with pytest.raises(TortoiseValidationError):
            MaxValueValidator(5)(value)

    @pytest.mark.parametrize("value", [0, 50, 100])
    def test_valid_range_0_100(self, value: int) -> None:
        """Verify values within 0-100 pass validation."""
        MinValueValidator(0)(value)
        MaxValueValidator(100)(value)

    def test_below_min_0_100(self) -> None:
        """Verify values below 0 raise ValidationError for 0-100 range."""
        with pytest.raises(TortoiseValidationError):
            MinValueValidator(0)(-1)

    def test_above_max_0_100(self) -> None:
        """Verify values above 100 raise ValidationError for 0-100 range."""
        with pytest.raises(TortoiseValidationError):
            MaxValueValidator(100)(101)

    def test_count_based_cost_multiplier_min_1(self) -> None:
        """Verify count_based_cost_multiplier rejects 0 (min is 1)."""
        with pytest.raises(TortoiseValidationError):
            MinValueValidator(1)(0)


class TestEmailFormatValidator:
    """Tests for custom email format validator."""

    @pytest.mark.parametrize(
        "value",
        [
            "user@example.com",
            "test.name@domain.org",
            "a@b.co",
            "user+tag@domain.com",
        ],
    )
    def test_valid_email(self, value: str) -> None:
        """Verify valid email addresses pass validation."""
        validate_email_format(value)

    @pytest.mark.parametrize(
        "value",
        [
            "not-an-email",
            "@missing-local.com",
            "missing-domain@",
            "no-dot@domain",
            "spaces in@email.com",
            "",
        ],
    )
    def test_invalid_email(self, value: str) -> None:
        """Verify invalid email addresses raise ValidationError."""
        with pytest.raises(TortoiseValidationError, match="Invalid email format"):
            validate_email_format(value)
