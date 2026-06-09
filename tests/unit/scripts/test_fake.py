"""Unit tests for the dev-data Faker helpers."""

import pytest
from scripts.dev_data import fake


@pytest.mark.parametrize(
    "generator",
    [
        fake.company_name,
        fake.campaign_title,
        fake.book_title,
        fake.chapter_title,
        fake.note_title,
        fake.quick_roll_name,
        fake.inventory_item_name,
    ],
)
def test_short_text_helpers_fit_char_50_min_3(generator) -> None:
    """Every text helper respects 3-50 character bounds across 200 samples."""
    # Given / When: many generated values
    values = [generator() for _ in range(200)]

    # Then: every value satisfies 3 <= len <= 50
    assert all(3 <= len(v) <= 50 for v in values), [v for v in values if not 3 <= len(v) <= 50]


def test_person_name_parts_are_valid() -> None:
    """Each generated name part satisfies the User name validators (min 2, max 50)."""
    # Given / When: a generated person
    first, last = fake.person_name()

    # Then: each part satisfies the User min-length-2 validator and the 50-char cap
    assert 2 <= len(first) <= 50
    assert 2 <= len(last) <= 50


def test_email_is_email_shaped() -> None:
    """Generated email contains @ and a domain with a dot."""
    # Given / When: a generated email
    email = fake.email()

    # Then: it looks like an email
    assert "@" in email
    assert "." in email.split("@")[-1]


def test_note_body_meets_min_length() -> None:
    """Generated note body meets the min-length-3 validator."""
    # Given / When: a generated note body
    body = fake.note_body()

    # Then: it satisfies the Note.content min-length-3 validator
    assert len(body) >= 3
