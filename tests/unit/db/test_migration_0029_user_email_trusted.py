"""Test the email_trusted backfill in migration 0029."""

import importlib
from typing import Any

import pytest
from tortoise import Tortoise

from vapi.db.sql_models.user import User

pytestmark = pytest.mark.anyio

migration = importlib.import_module("vapi.db.migrations.0029_user_email_trusted")


async def _run_backfill() -> None:
    await Tortoise.get_connection("default").execute_script(migration.BACKFILL_EMAIL_TRUSTED_SQL)


@pytest.mark.parametrize(
    ("profiles", "expected"),
    [
        ({"google_profile": {"id": "g1", "email": "Person@Example.com"}}, True),
        ({"apple_profile": {"id": "a1", "email": "person@example.com"}}, True),
        (
            {"discord_profile": {"id": "d1", "email": "person@example.com", "verified": True}},
            True,
        ),
        (
            {"discord_profile": {"id": "d1", "email": "person@example.com", "verified": False}},
            False,
        ),
        ({"github_profile": {"id": "h1", "email": "person@example.com"}}, False),
        ({"google_profile": {"id": "g1", "email": "someone-else@example.com"}}, False),
        ({}, False),
    ],
)
async def test_backfill_trusts_only_provider_proven_emails(
    company_factory, user_factory, profiles: dict[str, Any], expected: bool
) -> None:
    """Verify the backfill trusts an email only when a provider profile proves it."""
    # Given an untrusted user whose stored profiles may or may not prove the email
    company = await company_factory()
    user = await user_factory(
        company=company, email="person@example.com", email_trusted=False, **profiles
    )

    # When the backfill runs
    await _run_backfill()

    # Then trust matches whether a provider proved the email
    assert (await User.get(id=user.id)).email_trusted is expected
