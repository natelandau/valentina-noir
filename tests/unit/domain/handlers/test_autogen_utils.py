"""Test chargen utilities."""

from collections.abc import Callable
from typing import Any

import pytest

from vapi.constants import CharacterClass
from vapi.domain.handlers.character_autogeneration.constants import (
    MORTAL_CLASS_PERCENTILE,
    AutoGenExperienceLevel,
)
from vapi.domain.handlers.character_autogeneration.schemas import DotsPerExperienceLevel
from vapi.domain.handlers.character_autogeneration.utils import (
    adjust_trait_value_based_on_level,
    divide_total_randomly,
    get_character_class_from_percentile,
    get_character_class_percentile_lookup_table,
    shuffle_and_adjust_trait_values,
)

pytestmark = pytest.mark.anyio


class TestGetCharacterClassPercentile:
    """Test get_character_class_percentile_lookup_table function."""

    def test_returns_correct_percentile_lookup_table(self, debug: Callable[[Any], None]) -> None:
        """Verify the percentile is correct."""
        percentile = get_character_class_percentile_lookup_table()
        # debug(percentile)
        assert percentile[CharacterClass.MORTAL] == (0, MORTAL_CLASS_PERCENTILE)
        for lower_bound, upper_bound in percentile.values():
            assert lower_bound <= upper_bound
            assert lower_bound >= 0
            assert upper_bound <= 100


class TestGetClassFromPercentile:
    """Test get_class_from_percentile function."""

    @pytest.mark.parametrize(
        ("percentile", "expected_class"),
        [
            (1, CharacterClass.MORTAL),
            (30, CharacterClass.MORTAL),
            (MORTAL_CLASS_PERCENTILE, CharacterClass.MORTAL),
        ],
    )
    def test_returns_mortal_for_percentile_up_to_60(
        self, mocker, percentile: int, expected_class: CharacterClass
    ) -> None:
        """Verify MORTAL is returned for percentiles <= MORTAL_CLASS_PERCENTILE."""
        # Given a mocked percentile roll
        mocker.patch(
            "vapi.domain.handlers.character_autogeneration.utils.roll_percentile",
            return_value=percentile,
        )

        # When getting class from percentile
        result = get_character_class_from_percentile()

        # Then MORTAL should be returned
        assert result == expected_class

    def test_returns_non_mortal_for_percentile_above_60(self, mocker) -> None:
        """Verify non-MORTAL class is returned for percentiles > MORTAL_CLASS_PERCENTILE."""
        # Given a mocked percentile roll above 60
        mocker.patch(
            "vapi.domain.handlers.character_autogeneration.utils.roll_percentile",
            return_value=MORTAL_CLASS_PERCENTILE + 1,
        )

        # When getting class from percentile
        result = get_character_class_from_percentile()

        # Then a non-MORTAL class should be returned
        assert result != CharacterClass.MORTAL
        assert result in CharacterClass

    @pytest.mark.parametrize(
        "percentile",
        [MORTAL_CLASS_PERCENTILE + 1, 70, 80, 90, 100],
    )
    def test_returns_valid_class_for_high_percentiles(self, mocker, percentile: int) -> None:
        """Verify valid CharacterClass is returned for percentiles in MORTAL_CLASS_PERCENTILE + 1-100 range."""
        # Given a mocked percentile roll
        mocker.patch(
            "vapi.domain.handlers.character_autogeneration.utils.roll_percentile",
            return_value=percentile,
        )

        # When getting class from percentile
        result = get_character_class_from_percentile()

        # Then a valid CharacterClass should be returned
        assert isinstance(result, CharacterClass)
        assert result in CharacterClass

    def test_boundary_at_60_and_61(self, mocker) -> None:
        """Verify correct class assignment at the 60/61 boundary."""
        # Given percentile = 60
        mocker.patch(
            "vapi.domain.handlers.character_autogeneration.utils.roll_percentile",
            return_value=MORTAL_CLASS_PERCENTILE,
        )

        # When getting class from percentile
        result_60 = get_character_class_from_percentile()

        # Then MORTAL should be returned
        assert result_60 == CharacterClass.MORTAL

        # Given percentile = 61
        mocker.patch(
            "vapi.domain.handlers.character_autogeneration.utils.roll_percentile",
            return_value=MORTAL_CLASS_PERCENTILE + 1,
        )

        # When getting class from percentile
        result_61 = get_character_class_from_percentile()

        # Then non-MORTAL should be returned
        assert result_61 != CharacterClass.MORTAL

    def test_distribution_covers_all_percentiles(self, mocker) -> None:
        """Verify all percentiles from 1-100 return a valid class."""
        # Given all possible percentile values
        all_percentiles = range(1, 101)

        for percentile in all_percentiles:
            # Given a mocked percentile roll
            mocker.patch(
                "vapi.domain.handlers.character_autogeneration.utils.roll_percentile",
                return_value=percentile,
            )

            # When getting class from percentile
            result = get_character_class_from_percentile()

            # Then a valid CharacterClass should be returned
            assert isinstance(result, CharacterClass)
            assert result in CharacterClass

    def test_non_mortal_classes_are_distributed(self, mocker) -> None:
        """Verify non-MORTAL classes are assigned for percentiles 61-100."""
        # Given percentiles in the 61-100 range
        non_mortal_results = set()

        for percentile in range(MORTAL_CLASS_PERCENTILE + 1, 101):
            # Given a mocked percentile roll
            mocker.patch(
                "vapi.domain.handlers.character_autogeneration.utils.roll_percentile",
                return_value=percentile,
            )

            # When getting class from percentile
            result = get_character_class_from_percentile()

            # Then collect the result
            non_mortal_results.add(result)

        # Then multiple non-MORTAL classes should be assigned
        assert CharacterClass.MORTAL not in non_mortal_results
        assert len(non_mortal_results) > 1  # At least 2 different classes

    def test_last_percentile_returns_valid_class(self, mocker) -> None:
        """Verify percentile 100 returns a valid non-MORTAL class."""
        # Given percentile = 100
        mocker.patch(
            "vapi.domain.handlers.character_autogeneration.utils.roll_percentile", return_value=100
        )

        # When getting class from percentile
        result = get_character_class_from_percentile()

        # Then a valid non-MORTAL class should be returned
        assert isinstance(result, CharacterClass)
        assert result != CharacterClass.MORTAL


class TestDivideTotalRandomly:
    """Test divide_total_randomly function."""

    @pytest.mark.parametrize(
        ("total", "num", "max_value", "min_value"),
        [
            (10, 3, 4, 3),
            (10, 3, 5, 1),
            (20, 4, 8, 0),
            (30, 6, 8, 1),
            (30, 4, 9, 0),
            (30, 3, None, 0),
            (30, 3, 10, 0),
            (6, 2, None, 3),
        ],
    )
    def test_divide_total_randomly(self, total, num, max_value, min_value):
        """Test the divide_total_randomly function with various input combinations."""
        for _ in range(100):
            result = divide_total_randomly(total, num, max_value, min_value)

            assert len(result) == num
            assert sum(result) == total
            assert not any(x < min_value for x in result)
            if max_value:
                assert not any(x > max_value for x in result)

    def test_divide_total_randomly_raises_error(self) -> None:
        """Test that divide_total_randomly raises errors when it should."""
        with pytest.raises(ValueError, match="Impossible to divide"):
            divide_total_randomly(1, 2, min_value=1)

        with pytest.raises(ValueError, match="Impossible to divide"):
            divide_total_randomly(10, 2, 5, 6)

        with pytest.raises(ValueError, match="Impossible to divide"):
            divide_total_randomly(10, 2, 3)


class TestShuffleAndAdjustTraitValues:
    """Test shuffle_and_adjust_trait_values function."""

    @pytest.mark.parametrize(
        ("experience_level", "dot_bonus_value"),
        [
            (AutoGenExperienceLevel.NEW, 0),
            (AutoGenExperienceLevel.INTERMEDIATE, 3),
            (AutoGenExperienceLevel.ADVANCED, 5),
            (AutoGenExperienceLevel.ELITE, 7),
        ],
    )
    def test_uses_correct_dot_bonus_for_experience_level(
        self, mocker, experience_level: AutoGenExperienceLevel, dot_bonus_value: int
    ) -> None:
        """Verify correct dot bonus is used for each experience level."""
        # Given trait values and dot bonus
        trait_values = [1, 2, 3]
        original_sum = sum(trait_values)
        dot_bonus = DotsPerExperienceLevel(NEW=0, INTERMEDIATE=3, ADVANCED=5, ELITE=7)

        # When shuffling and adjusting trait values
        result = shuffle_and_adjust_trait_values(trait_values, experience_level, dot_bonus)

        # Then correct number of dots should be added
        expected_sum = original_sum + dot_bonus_value
        assert sum(result) == expected_sum

    def test_adds_dots_to_traits_below_five(self, mocker) -> None:
        """Verify dots are only added to traits below 5."""
        # Given trait values with some at 5
        trait_values = [1, 2, 5, 3, 5]
        original_sum = sum(trait_values)
        original_fives_indices = [i for i, v in enumerate(trait_values) if v == 5]
        dot_bonus = DotsPerExperienceLevel(NEW=0, INTERMEDIATE=3, ADVANCED=0, ELITE=0)
        # Mock randint to select indices 0, 1, 3 (all below 5)
        mocker.patch(
            "vapi.domain.handlers.character_autogeneration.utils.random.randint",
            side_effect=[0, 1, 3],
        )
        mocker.patch(
            "vapi.domain.handlers.character_autogeneration.utils.random.sample",
            side_effect=lambda x, k: list(x),
        )

        # When shuffling and adjusting trait values
        result = shuffle_and_adjust_trait_values(
            trait_values, AutoGenExperienceLevel.INTERMEDIATE, dot_bonus
        )

        # Then traits at 5 should remain at 5
        for idx in original_fives_indices:
            assert result[idx] == 5
        # And correct number of dots should be added
        assert sum(result) == original_sum + 3

    def test_skips_traits_at_five_when_adding_dots(self, mocker) -> None:
        """Verify traits at 5 are skipped when adding dots."""
        # Given trait values where some are at 5
        trait_values = [5, 5, 2, 3]
        original_sum = sum(trait_values)
        dot_bonus = DotsPerExperienceLevel(NEW=0, INTERMEDIATE=2, ADVANCED=0, ELITE=0)
        # Mock randint to potentially select indices with 5s, but function should skip them
        call_count = [0]

        def side_effect(*args: int) -> int:
            call_count[0] += 1
            # Return indices 2, 3 (both below 5) after potentially trying 0 or 1
            if call_count[0] <= 2:
                return 2 if call_count[0] == 1 else 3
            return 2

        mocker.patch(
            "vapi.domain.handlers.character_autogeneration.utils.random.randint",
            side_effect=side_effect,
        )
        mocker.patch(
            "vapi.domain.handlers.character_autogeneration.utils.random.sample",
            side_effect=lambda x, k: list(x),
        )

        # When shuffling and adjusting trait values
        result = shuffle_and_adjust_trait_values(
            trait_values, AutoGenExperienceLevel.INTERMEDIATE, dot_bonus
        )

        # Then traits at 5 should remain at 5
        assert result[0] == 5
        assert result[1] == 5
        # And dots should be added to other traits
        assert sum(result) == original_sum + 2

    def test_shuffles_result(self, mocker) -> None:
        """Verify result is shuffled."""
        # Given trait values
        trait_values = [1, 2, 3, 4]
        dot_bonus = DotsPerExperienceLevel(NEW=0, INTERMEDIATE=0, ADVANCED=0, ELITE=0)
        # Mock sample to return reversed list to verify shuffling occurs
        mock_sample = mocker.patch(
            "vapi.domain.handlers.character_autogeneration.utils.random.sample",
            return_value=[4, 3, 2, 1],
        )

        # When shuffling and adjusting trait values
        result = shuffle_and_adjust_trait_values(
            trait_values, AutoGenExperienceLevel.NEW, dot_bonus
        )

        # Then result should be shuffled
        assert result == [4, 3, 2, 1]
        mock_sample.assert_called_once_with(trait_values, len(trait_values))

    def test_handles_zero_dot_bonus(self) -> None:
        """Verify function handles zero dot bonus correctly."""
        # Given trait values and zero dot bonus
        trait_values = [1, 2, 3]
        dot_bonus = DotsPerExperienceLevel(NEW=0, INTERMEDIATE=0, ADVANCED=0, ELITE=0)

        # When shuffling and adjusting trait values
        result = shuffle_and_adjust_trait_values(
            trait_values, AutoGenExperienceLevel.NEW, dot_bonus
        )

        # Then no dots should be added, only shuffled
        assert sum(result) == sum(trait_values)
        assert len(result) == len(trait_values)

    def test_handles_all_traits_at_five(self) -> None:
        """Verify function handles all traits at 5 correctly with zero dot bonus."""
        # Given all trait values at 5 and zero dot bonus
        trait_values = [5, 5, 5]
        dot_bonus = DotsPerExperienceLevel(NEW=0, INTERMEDIATE=0, ADVANCED=0, ELITE=0)

        # When shuffling and adjusting trait values
        result = shuffle_and_adjust_trait_values(
            trait_values, AutoGenExperienceLevel.INTERMEDIATE, dot_bonus
        )

        # Then all traits should remain at 5 (no dots can be added)
        assert all(x == 5 for x in result)
        assert sum(result) == sum(trait_values)

    def test_handles_empty_trait_values(self) -> None:
        """Verify function handles empty trait values list with zero dot bonus."""
        # Given empty trait values and zero dot bonus
        trait_values: list[int] = []
        dot_bonus = DotsPerExperienceLevel(NEW=0, INTERMEDIATE=0, ADVANCED=0, ELITE=0)

        # When shuffling and adjusting trait values
        result = shuffle_and_adjust_trait_values(
            trait_values, AutoGenExperienceLevel.INTERMEDIATE, dot_bonus
        )

        # Then empty list should be returned
        assert result == []
        assert len(result) == 0

    def test_adds_multiple_dots_to_same_trait(self, mocker) -> None:
        """Verify multiple dots can be added to the same trait if below 5."""
        # Given trait values and dot bonus that adds multiple dots
        trait_values = [1, 2]
        original_sum = sum(trait_values)
        dot_bonus = DotsPerExperienceLevel(NEW=0, INTERMEDIATE=3, ADVANCED=0, ELITE=0)
        # Mock randint to select index 0 three times
        mocker.patch(
            "vapi.domain.handlers.character_autogeneration.utils.random.randint", return_value=0
        )

        # When shuffling and adjusting trait values
        result = shuffle_and_adjust_trait_values(
            trait_values, AutoGenExperienceLevel.INTERMEDIATE, dot_bonus
        )

        # Then trait at index 0 should have 3 dots added (1 + 3 = 4)
        assert result in [[4, 2], [2, 4]]
        assert sum(result) == original_sum + 3

    def test_adds_dots_until_traits_reach_five(self, mocker) -> None:
        """Verify function adds dots until traits reach 5 when exactly enough dots are provided."""
        # Given trait values close to 5 and exactly enough dots to bring them all to 5
        trait_values = [4, 4, 4]
        original_sum = sum(trait_values)
        dot_bonus = DotsPerExperienceLevel(NEW=0, INTERMEDIATE=3, ADVANCED=0, ELITE=0)
        # Mock randint to select each index once (0, 1, 2)
        mocker.patch(
            "vapi.domain.handlers.character_autogeneration.utils.random.randint",
            side_effect=[0, 1, 2],
        )

        # When shuffling and adjusting trait values
        result = shuffle_and_adjust_trait_values(
            trait_values, AutoGenExperienceLevel.INTERMEDIATE, dot_bonus
        )

        # Then all traits should be at 5 (exactly 3 dots added)
        assert all(x == 5 for x in result)
        assert sum(result) == 15
        assert sum(result) == original_sum + 3

    def test_stops_iterating_when_all_traits_are_at_max_value(self) -> None:
        """Verify function stops iterating when all traits are at max value."""
        # Given trait values at max value and dot bonus that adds dots
        trait_values = [3, 4, 4]
        dot_bonus = DotsPerExperienceLevel(NEW=0, INTERMEDIATE=3, ADVANCED=0, ELITE=0)

        # When shuffling and adjusting trait values
        result = shuffle_and_adjust_trait_values(
            trait_values, AutoGenExperienceLevel.INTERMEDIATE, dot_bonus, max_value=4
        )
        assert all(x == 4 for x in result)


class TestAdjustTraitValueBasedOnLevel:
    """Test adjust_trait_value_based_on_level function."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (1, 1),
            (2, 2),
            (3, 2),
            (4, 2),
            (5, 2),
            (10, 2),
        ],
    )
    def test_new_level_caps_at_two(self, value: int, expected: int) -> None:
        """Verify NEW level caps trait value at 2."""
        # Given a trait value and NEW experience level
        # When adjusting the trait value
        result = adjust_trait_value_based_on_level(AutoGenExperienceLevel.NEW, value)

        # Then value should be capped at 2
        assert result == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (1, 1),
            (2, 2),
            (3, 3),
            (4, 3),
            (5, 3),
            (10, 3),
        ],
    )
    def test_intermediate_level_caps_at_three(self, value: int, expected: int) -> None:
        """Verify INTERMEDIATE level caps trait value at 3."""
        # Given a trait value and INTERMEDIATE experience level
        # When adjusting the trait value
        result = adjust_trait_value_based_on_level(AutoGenExperienceLevel.INTERMEDIATE, value)

        # Then value should be capped at 3
        assert result == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (1, 2),
            (2, 3),
            (3, 4),
            (4, 5),
            (5, 5),
        ],
    )
    def test_advanced_level_increments_by_one(self, value: int, expected: int) -> None:
        """Verify ADVANCED level increments trait value by 1."""
        # Given a trait value and ADVANCED experience level
        # When adjusting the trait value
        result = adjust_trait_value_based_on_level(AutoGenExperienceLevel.ADVANCED, value)

        # Then value should be incremented by 1, capped at max_value
        assert result == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (1, 2),
            (2, 3),
            (3, 4),
            (4, 5),
            (5, 5),
        ],
    )
    def test_elite_level_increments_by_one(self, value: int, expected: int) -> None:
        """Verify ELITE level increments trait value by 1."""
        # Given a trait value and ELITE experience level
        # When adjusting the trait value
        result = adjust_trait_value_based_on_level(AutoGenExperienceLevel.ELITE, value)

        # Then value should be incremented by 1, capped at max_value
        assert result == expected

    @pytest.mark.parametrize(
        ("experience_level", "value", "max_value", "expected"),
        [
            (AutoGenExperienceLevel.NEW, 5, 2, 2),
            (AutoGenExperienceLevel.NEW, 5, 1, 1),
            (AutoGenExperienceLevel.INTERMEDIATE, 5, 3, 3),
            (AutoGenExperienceLevel.INTERMEDIATE, 5, 2, 2),
            (AutoGenExperienceLevel.ADVANCED, 4, 4, 4),
            (AutoGenExperienceLevel.ADVANCED, 5, 4, 4),
            (AutoGenExperienceLevel.ELITE, 4, 3, 3),
            (AutoGenExperienceLevel.ELITE, 5, 3, 3),
        ],
    )
    def test_respects_custom_max_value(
        self,
        experience_level: AutoGenExperienceLevel,
        value: int,
        max_value: int,
        expected: int,
    ) -> None:
        """Verify function respects custom max_value parameter."""
        # Given a trait value, experience level, and custom max_value
        # When adjusting the trait value
        result = adjust_trait_value_based_on_level(experience_level, value, max_value=max_value)

        # Then value should not exceed max_value
        assert result == expected
        assert result <= max_value

    @pytest.mark.parametrize(
        ("experience_level", "value", "min_value", "expected"),
        [
            (AutoGenExperienceLevel.NEW, 0, 1, 1),
            (AutoGenExperienceLevel.NEW, -1, 1, 1),
            (AutoGenExperienceLevel.INTERMEDIATE, 0, 1, 1),
            (AutoGenExperienceLevel.ADVANCED, 0, 1, 1),
            (AutoGenExperienceLevel.ADVANCED, -1, 1, 1),
            (AutoGenExperienceLevel.ELITE, 0, 1, 1),
            (AutoGenExperienceLevel.NEW, 1, 2, 2),
            (AutoGenExperienceLevel.INTERMEDIATE, 1, 2, 2),
        ],
    )
    def test_respects_custom_min_value(
        self,
        experience_level: AutoGenExperienceLevel,
        value: int,
        min_value: int,
        expected: int,
    ) -> None:
        """Verify function respects custom min_value parameter."""
        # Given a trait value, experience level, and custom min_value
        # When adjusting the trait value
        result = adjust_trait_value_based_on_level(experience_level, value, min_value=min_value)

        # Then value should not be below min_value
        assert result == expected
        assert result >= min_value

    @pytest.mark.parametrize(
        ("experience_level", "value", "min_value", "max_value", "expected"),
        [
            (AutoGenExperienceLevel.NEW, 5, 1, 2, 2),
            (AutoGenExperienceLevel.NEW, 0, 1, 2, 1),
            (AutoGenExperienceLevel.INTERMEDIATE, 5, 1, 3, 3),
            (AutoGenExperienceLevel.INTERMEDIATE, 0, 1, 3, 1),
            (AutoGenExperienceLevel.ADVANCED, 5, 1, 5, 5),
            (AutoGenExperienceLevel.ADVANCED, 0, 1, 5, 1),
            (AutoGenExperienceLevel.ELITE, 5, 1, 5, 5),
            (AutoGenExperienceLevel.ELITE, 0, 1, 5, 1),
        ],
    )
    def test_respects_both_min_and_max_value(
        self,
        experience_level: AutoGenExperienceLevel,
        value: int,
        min_value: int,
        max_value: int,
        expected: int,
    ) -> None:
        """Verify function respects both min_value and max_value parameters."""
        # Given a trait value, experience level, and custom min/max values
        # When adjusting the trait value
        result = adjust_trait_value_based_on_level(
            experience_level, value, max_value=max_value, min_value=min_value
        )

        # Then value should be within the min/max range
        assert result == expected
        assert min_value <= result <= max_value

    def test_zero_value_with_new_level(self) -> None:
        """Verify NEW level handles zero value correctly."""
        # Given a zero trait value and NEW experience level
        # When adjusting the trait value
        result = adjust_trait_value_based_on_level(AutoGenExperienceLevel.NEW, 0)

        # Then value should be clamped to min_value (1)
        assert result == 1

    def test_zero_value_with_advanced_level(self) -> None:
        """Verify ADVANCED level increments zero value correctly."""
        # Given a zero trait value and ADVANCED experience level
        # When adjusting the trait value
        result = adjust_trait_value_based_on_level(AutoGenExperienceLevel.ADVANCED, 0)

        # Then value should be incremented to 1
        assert result == 1

    def test_negative_value_with_new_level(self) -> None:
        """Verify NEW level handles negative value correctly."""
        # Given a negative trait value and NEW experience level
        # When adjusting the trait value
        result = adjust_trait_value_based_on_level(AutoGenExperienceLevel.NEW, -5)

        # Then value should be clamped to min_value (1)
        assert result == 1

    def test_negative_value_with_elite_level(self) -> None:
        """Verify ELITE level increments negative value correctly."""
        # Given a negative trait value and ELITE experience level
        # When adjusting the trait value
        result = adjust_trait_value_based_on_level(AutoGenExperienceLevel.ELITE, -5)

        # Then value should be incremented then clamped to min_value (1)
        assert result == 1

    def test_high_value_with_advanced_level(self) -> None:
        """Verify ADVANCED level caps high value correctly."""
        # Given a high trait value and ADVANCED experience level
        # When adjusting the trait value
        result = adjust_trait_value_based_on_level(AutoGenExperienceLevel.ADVANCED, 10)

        # Then value should be incremented then capped at max_value (5)
        assert result == 5

    def test_high_value_with_elite_level(self) -> None:
        """Verify ELITE level caps high value correctly."""
        # Given a high trait value and ELITE experience level
        # When adjusting the trait value
        result = adjust_trait_value_based_on_level(AutoGenExperienceLevel.ELITE, 10)

        # Then value should be incremented then capped at max_value (5)
        assert result == 5
