"""Test the gameplay lib."""

from __future__ import annotations

import pytest

from vapi.constants import DiceSize, RollResultType
from vapi.db.models.diceroll import DiceRollResultSchema
from vapi.domain.handlers.diceroll_handler import (
    _calculate_result_type,
    _count_dice_results,
    roll_dice,
)

pytestmark = pytest.mark.anyio


class TestDiceRollResult:
    """Verify DiceRollResult computed properties."""

    def test_total_dice_roll_emoji(self) -> None:
        """Verify total_dice_roll_emoji returns correct emoji string."""
        # Given a dice roll result
        result = DiceRollResultSchema(
            total_result=3,
            total_result_type=RollResultType.SUCCESS,
            total_result_humanized="3 Successes",
            total_dice_roll=[1, 3, 5],
            player_roll=[1, 3],
            desperation_roll=[5],
        )

        # When getting the emoji string
        # Then it returns the correct string
        assert result.total_dice_roll_emoji == "1️⃣ 3️⃣ 5️⃣"

    def test_total_dice_roll_shortcode(self) -> None:
        """Verify total_dice_roll_shortcode returns correct shortcode string."""
        # Given a dice roll result
        result = DiceRollResultSchema(
            total_result=3,
            total_result_type=RollResultType.SUCCESS,
            total_result_humanized="3 Successes",
            total_dice_roll=[1, 3, 5],
            player_roll=[1, 3],
            desperation_roll=[5],
        )

        # When getting the shortcode string
        # Then it returns the correct string
        assert result.total_dice_roll_shortcode == ":one: :three: :five:"

    def test_player_roll_emoji(self) -> None:
        """Verify player_roll_emoji returns correct emoji string."""
        # Given a dice roll result
        result = DiceRollResultSchema(
            total_result=3,
            total_result_type=RollResultType.SUCCESS,
            total_result_humanized="3 Successes",
            total_dice_roll=[1, 3, 5],
            player_roll=[1, 3],
            desperation_roll=[5],
        )

        # When getting the emoji string
        # Then it returns the correct string
        assert result.player_roll_emoji == "1️⃣ 3️⃣"

    def test_player_roll_shortcode(self) -> None:
        """Verify player_roll_shortcode returns correct shortcode string."""
        # Given a dice roll result
        result = DiceRollResultSchema(
            total_result=3,
            total_result_type=RollResultType.SUCCESS,
            total_result_humanized="3 Successes",
            total_dice_roll=[1, 3, 5],
            player_roll=[1, 3],
            desperation_roll=[5],
        )

        # When getting the shortcode string
        # Then it returns the correct string
        assert result.player_roll_shortcode == ":one: :three:"

    def test_desperation_roll_emoji(self) -> None:
        """Verify desperation_roll_emoji returns correct emoji string."""
        # Given a dice roll result
        result = DiceRollResultSchema(
            total_result=3,
            total_result_type=RollResultType.SUCCESS,
            total_result_humanized="3 Successes",
            total_dice_roll=[1, 3, 5],
            player_roll=[1, 3],
            desperation_roll=[5],
        )

        # When getting the emoji string
        # Then it returns the correct string
        assert result.desperation_roll_emoji == "5️⃣"

    def test_desperation_roll_shortcode(self) -> None:
        """Verify desperation_roll_shortcode returns correct shortcode string."""
        # Given a dice roll result
        result = DiceRollResultSchema(
            total_result=3,
            total_result_type=RollResultType.SUCCESS,
            total_result_humanized="3 Successes",
            total_dice_roll=[1, 3, 5],
            player_roll=[1, 3],
            desperation_roll=[5],
        )

        # When getting the shortcode string
        # Then it returns the correct string
        assert result.desperation_roll_shortcode == ":five:"


class TestCalculateResultType:
    """Verify calculate_result_type function."""

    @pytest.mark.parametrize(
        ("result", "dice_size", "expected_type", "expected_humanized"),
        [
            (-1, DiceSize.D10, RollResultType.BOTCH, "-1 Successes"),
            (0, DiceSize.D10, RollResultType.FAILURE, "0 Successes"),
            (5, DiceSize.D10, RollResultType.SUCCESS, "5 Successes"),
            (1, DiceSize.D10, RollResultType.SUCCESS, "1 Success"),
            (11, DiceSize.D10, RollResultType.CRITICAL, "11 Successes"),
            (5, DiceSize.D6, RollResultType.OTHER, ""),
        ],
    )
    def test_calculate_result_type(
        self,
        result: int,
        dice_size: DiceSize,
        expected_type: RollResultType,
        expected_humanized: str,
    ) -> None:
        """Verify calculate_result_type returns correct result type and humanized string."""
        # When calculating the result type
        result_type, result_humanized = _calculate_result_type(
            result=result, dice_size=dice_size, num_dice=5
        )

        # Then it returns the correct type and humanized string
        assert result_type == expected_type
        assert result_humanized == expected_humanized


class TestCountDiceResults:
    """Verify _count_dice_results function."""

    @pytest.mark.parametrize(
        (
            "roll",
            "difficulty",
            "dice_max",
            "expected_botches",
            "expected_failures",
            "expected_successes",
            "expected_criticals",
        ),
        [
            (
                [1, 1, 5, 10],  # roll
                6,  # difficulty
                10,  # dice_max
                2,  # expected_botches
                1,  # expected_failures
                0,  # expected_successes
                1,  # expected_criticals
            ),  # Two botches, one failure, one success, one critical
            ([6, 7, 8], 6, 10, 0, 0, 3, 0),  # All successes
            ([1, 2, 3], 6, 10, 1, 2, 0, 0),  # One botch, two failures
            ([10, 10], 6, 10, 0, 0, 0, 2),  # All criticals
            ([1, 10], 6, 10, 1, 0, 0, 1),  # One botch, one critical
        ],
    )
    def test_count_dice_results(
        self,
        roll: list[int],
        difficulty: int,
        dice_max: int,
        expected_botches: int,
        expected_failures: int,
        expected_successes: int,
        expected_criticals: int,
    ) -> None:
        """Verify _count_dice_results counts dice results correctly."""
        # When counting dice results
        counts = _count_dice_results(roll=roll, difficulty=difficulty, dice_max=dice_max)

        # Then it returns the correct counts
        assert counts.botches == expected_botches
        assert counts.failures == expected_failures
        assert counts.successes == expected_successes
        assert counts.criticals == expected_criticals


class TestRollDice:
    """Verify roll_dice function."""

    def test_roll_dice_returns_dice_roll_result(self, mocker) -> None:
        """Verify roll_dice returns a DiceRollResult object."""
        # Given mocked random numbers
        mocker.patch("vapi.domain.handlers.diceroll_handler.random_num", side_effect=[5, 7, 1])

        # When rolling dice
        result = roll_dice(num_dice=2, num_desperation_dice=1, difficulty=6, dice_size=DiceSize.D10)

        # Then it returns a DiceRollResult object
        assert isinstance(result, DiceRollResultSchema)
        assert result.player_roll == [5, 7]
        assert result.desperation_roll == [1]
        assert result.total_dice_roll == [1, 5, 7]

    @pytest.mark.parametrize(
        (
            "player_rolls",
            "desperation_rolls",
            "difficulty",
            "dice_size",
            "expected_result",
            "expected_type",
        ),
        [
            # D10 tests with difficulty
            ([7, 8], [9], 6, DiceSize.D10, 3, RollResultType.SUCCESS),  # 3 successes
            (
                [1, 1],
                [10],
                6,
                DiceSize.D10,
                -1,
                RollResultType.BOTCH,
            ),
            (
                [10, 10],
                [10],
                6,
                DiceSize.D10,
                6,
                RollResultType.CRITICAL,
            ),  # 3 criticals (double count)
            ([1, 2, 3], [4, 5], 6, DiceSize.D10, -1, RollResultType.BOTCH),  # 1 botch, 4 failures
            # # D6 tests with difficulty
            ([3, 4], [5], 4, DiceSize.D6, 1, RollResultType.OTHER),
            # # Tests without difficulty
            ([3, 4], [5], None, DiceSize.D10, None, RollResultType.OTHER),
        ],
    )
    def test_roll_dice_calculation(
        self,
        mocker,
        player_rolls: list[int],
        desperation_rolls: list[int],
        difficulty: int | None,
        dice_size: DiceSize,
        expected_result: int | None,
        expected_type: RollResultType,
    ) -> None:
        """Verify roll_dice calculates results correctly."""
        # Given mocked random numbers
        mocker.patch(
            "vapi.domain.handlers.diceroll_handler.random_num",
            side_effect=player_rolls + desperation_rolls,
        )

        # When rolling dice
        result = roll_dice(
            num_dice=len(player_rolls),
            num_desperation_dice=len(desperation_rolls),
            difficulty=difficulty,
            dice_size=dice_size,
        )

        # Then it returns the expected result
        assert result.total_result == expected_result
        assert result.total_result_type == expected_type
        assert result.player_roll == sorted(player_rolls)
        assert result.desperation_roll == sorted(desperation_rolls)
        assert result.total_dice_roll == sorted(player_rolls + desperation_rolls)
