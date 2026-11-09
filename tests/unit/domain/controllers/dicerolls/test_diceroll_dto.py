"""Unit tests for dice roll request DTOs."""

import msgspec
import pytest

from vapi.constants import (
    MAX_DESPERATION,
    MAX_DICE_ROLL_COMMENT_LENGTH,
    MAX_DICE_ROLL_TRAITS,
    MAX_NUM_DICE,
    DiceSize,
)
from vapi.domain.controllers.dicerolls.dto import DiceRollCreate, QuickRollRequest
from vapi.domain.controllers.user.dto import QuickRollCreate, QuickRollPatch

TRAIT_ID = "01a18f5f-2849-738b-9e25-191c14ec3bb4"


@pytest.mark.parametrize(
    ("payload"),
    [
        {"num_dice": MAX_NUM_DICE + 1},
        {"num_dice": -1},
        {"num_desperation_dice": MAX_DESPERATION + 1},
        {"num_desperation_dice": -1},
    ],
)
def test_dice_roll_create_rejects_out_of_range_counts(payload: dict[str, int]) -> None:
    """Verify DiceRollCreate rejects dice counts outside the allowed range."""
    # Given a request body with an out-of-range dice count
    # When decoding it
    # Then msgspec rejects it before any dice are rolled
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert(payload, DiceRollCreate)


def test_dice_roll_create_accepts_maximum_counts() -> None:
    """Verify DiceRollCreate accepts the largest allowed dice counts."""
    # Given a request body at the upper bounds
    payload = {"num_dice": MAX_NUM_DICE, "num_desperation_dice": MAX_DESPERATION}

    # When decoding it
    data = msgspec.convert(payload, DiceRollCreate)

    # Then the counts are kept
    assert data.num_dice == MAX_NUM_DICE
    assert data.num_desperation_dice == MAX_DESPERATION


def test_quickroll_request_rejects_too_many_desperation_dice() -> None:
    """Verify QuickRollRequest rejects more desperation dice than the maximum."""
    # Given a quick roll body with too many desperation dice
    payload = {
        "quickroll_id": "01a18f5f-2849-738b-9e25-191c14ec3bb2",
        "character_id": "01a18f5f-2849-738b-9e25-191c14ec3bb3",
        "num_desperation_dice": MAX_DESPERATION + 1,
    }

    # When decoding it
    # Then msgspec rejects it
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert(payload, QuickRollRequest)


@pytest.mark.parametrize(
    ("payload"),
    [
        {"comment": "x" * (MAX_DICE_ROLL_COMMENT_LENGTH + 1)},
        {"trait_ids": [TRAIT_ID] * (MAX_DICE_ROLL_TRAITS + 1)},
    ],
)
def test_dice_roll_create_rejects_oversized_comment_and_traits(payload: dict) -> None:
    """Verify DiceRollCreate rejects comments and trait lists over their caps."""
    # Given a request body with an oversized comment or trait list
    # When decoding it
    # Then msgspec rejects it
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert(payload, DiceRollCreate)


def test_dice_roll_create_accepts_maximum_comment_and_traits() -> None:
    """Verify DiceRollCreate accepts a comment and trait list at their caps."""
    # Given a request body at the comment and trait caps
    payload = {
        "comment": "x" * MAX_DICE_ROLL_COMMENT_LENGTH,
        "trait_ids": [TRAIT_ID] * MAX_DICE_ROLL_TRAITS,
    }

    # When decoding it
    data = msgspec.convert(payload, DiceRollCreate)

    # Then both are kept
    assert len(data.comment) == MAX_DICE_ROLL_COMMENT_LENGTH
    assert len(data.trait_ids) == MAX_DICE_ROLL_TRAITS


def test_quickroll_request_rejects_oversized_comment() -> None:
    """Verify QuickRollRequest rejects a comment over the cap."""
    # Given a quick roll body with an oversized comment
    payload = {
        "quickroll_id": "01a18f5f-2849-738b-9e25-191c14ec3bb2",
        "character_id": "01a18f5f-2849-738b-9e25-191c14ec3bb3",
        "comment": "x" * (MAX_DICE_ROLL_COMMENT_LENGTH + 1),
    }

    # When decoding it
    # Then msgspec rejects it
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert(payload, QuickRollRequest)


@pytest.mark.parametrize("struct", [QuickRollCreate, QuickRollPatch])
def test_quickroll_definition_rejects_too_many_traits(struct: type) -> None:
    """Verify saved quick rolls reject trait lists over the cap."""
    # Given a quick roll definition with too many traits
    payload = {"name": "Punch", "trait_ids": [TRAIT_ID] * (MAX_DICE_ROLL_TRAITS + 1)}

    # When decoding it
    # Then msgspec rejects it
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert(payload, struct)


@pytest.mark.parametrize("difficulty", [-1, int(max(DiceSize)) + 1])
@pytest.mark.parametrize("model", [DiceRollCreate, QuickRollRequest])
def test_difficulty_out_of_range_is_rejected(difficulty: int, model: type) -> None:
    """Verify both roll DTOs reject a difficulty below 0 or above the largest die size."""
    # Given a request body with an out-of-range difficulty
    payload = {"quickroll_id": TRAIT_ID, "character_id": TRAIT_ID, "difficulty": difficulty}

    # When decoding it
    # Then msgspec rejects it
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert(payload, model)


@pytest.mark.parametrize("difficulty", [0, int(max(DiceSize))])
@pytest.mark.parametrize("model", [DiceRollCreate, QuickRollRequest])
def test_difficulty_at_bounds_is_accepted(difficulty: int, model: type) -> None:
    """Verify both roll DTOs accept the lowest and highest allowed difficulty."""
    # Given a request body at a difficulty bound
    payload = {"quickroll_id": TRAIT_ID, "character_id": TRAIT_ID, "difficulty": difficulty}

    # When decoding it
    result = msgspec.convert(payload, model)

    # Then the difficulty is kept
    assert result.difficulty == difficulty


QUICKROLL_IDS = {
    "quickroll_id": "01a18f5f-2849-738b-9e25-191c14ec3bb2",
    "character_id": "01a18f5f-2849-738b-9e25-191c14ec3bb3",
}


@pytest.mark.parametrize(
    ("model", "base"), [(DiceRollCreate, {}), (QuickRollRequest, QUICKROLL_IDS)]
)
def test_dice_modifier_defaults_to_zero(model: type, base: dict) -> None:
    """Verify a request without a dice modifier gets a modifier of 0."""
    # Given a request body with no dice modifier
    # When decoding it
    data = msgspec.convert(base, model)

    # Then the modifier is 0
    assert data.dice_modifier == 0


@pytest.mark.parametrize("modifier", [-MAX_NUM_DICE, MAX_NUM_DICE])
@pytest.mark.parametrize(
    ("model", "base"), [(DiceRollCreate, {}), (QuickRollRequest, QUICKROLL_IDS)]
)
def test_dice_modifier_accepts_bounds(model: type, base: dict, modifier: int) -> None:
    """Verify the dice modifier accepts values at both ends of its range."""
    # Given a request body with a modifier at a bound
    payload = {**base, "dice_modifier": modifier}

    # When decoding it
    data = msgspec.convert(payload, model)

    # Then the modifier is kept
    assert data.dice_modifier == modifier


@pytest.mark.parametrize("modifier", [-MAX_NUM_DICE - 1, MAX_NUM_DICE + 1])
@pytest.mark.parametrize(
    ("model", "base"), [(DiceRollCreate, {}), (QuickRollRequest, QUICKROLL_IDS)]
)
def test_dice_modifier_rejects_out_of_range(model: type, base: dict, modifier: int) -> None:
    """Verify the dice modifier rejects values outside its range."""
    # Given a request body with an out-of-range modifier
    payload = {**base, "dice_modifier": modifier}

    # When decoding it
    # Then msgspec rejects it
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert(payload, model)
