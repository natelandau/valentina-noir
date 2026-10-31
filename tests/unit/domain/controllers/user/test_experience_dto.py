"""Unit tests for the XP request DTO."""

from uuid import uuid4

import msgspec
import pytest

from vapi.constants import MAX_EXPERIENCE_GRANT
from vapi.domain.controllers.user.dto import ExperienceAddRemove


@pytest.mark.parametrize("amount", [0, -5])
def test_experience_amount_must_be_positive(amount: int) -> None:
    """Verify a zero or negative XP amount is rejected before it reaches the ledger."""
    # Given a request body with a non-positive amount
    body = {"amount": amount, "campaign_id": str(uuid4())}

    # When/Then decoding it fails validation
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert(body, ExperienceAddRemove)


def test_experience_amount_above_cap_is_rejected() -> None:
    """Verify an amount above the per-request cap is rejected before it reaches the ledger."""
    # Given a request body one above the cap
    body = {"amount": MAX_EXPERIENCE_GRANT + 1, "campaign_id": str(uuid4())}

    # When/Then decoding it fails validation
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert(body, ExperienceAddRemove)


def test_experience_amount_at_cap_is_accepted() -> None:
    """Verify the cap itself is a valid amount."""
    # Given a request body at the cap
    body = {"amount": MAX_EXPERIENCE_GRANT, "campaign_id": str(uuid4())}

    # When decoding it
    result = msgspec.convert(body, ExperienceAddRemove)

    # Then the amount is kept
    assert result.amount == MAX_EXPERIENCE_GRANT
