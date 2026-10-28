"""Unit tests for the XP request DTO."""

from uuid import uuid4

import msgspec
import pytest

from vapi.domain.controllers.user.dto import ExperienceAddRemove


@pytest.mark.parametrize("amount", [0, -5])
def test_experience_amount_must_be_positive(amount: int) -> None:
    """Verify a zero or negative XP amount is rejected before it reaches the ledger."""
    # Given a request body with a non-positive amount
    body = {"amount": amount, "campaign_id": str(uuid4())}

    # When/Then decoding it fails validation
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert(body, ExperienceAddRemove)
