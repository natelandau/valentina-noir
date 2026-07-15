"""Tests for BaseModel archive-stamp and primary-key invariants."""

from typing import TYPE_CHECKING

import pytest

from vapi.db.sql_models.company import Company

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


async def test_id_default_compares_equal_after_db_round_trip(
    company_factory: "Callable[..., Company]",
) -> None:
    """Verify a freshly minted id still compares equal once Postgres reads it back."""
    # Given an id minted by the primary key default
    minted_id = Company._meta.fields_map["id"].default()

    # When a row created with it is read back from Postgres
    company = await company_factory(id=minted_id)

    # Then the two ids compare equal and match as dict keys, so Tortoise's in-Python
    # prefetch matching cannot silently miss on an instance that was never refetched
    assert company.id == minted_id
    assert minted_id == company.id
    assert {minted_id: "hit"}.get(company.id) == "hit"


async def test_save_archive_mints_date_and_batch(
    company_factory: "Callable[..., Company]",
) -> None:
    """Verify saving an archived row mints both archive_date and archive_batch_id."""
    # Given an active company
    company = await company_factory(is_archived=False)

    # When it is archived via save()
    company.is_archived = True
    await company.save()

    # Then both stamps are populated
    refreshed = await Company.get(id=company.id)
    assert refreshed.archive_date is not None
    assert refreshed.archive_batch_id is not None


async def test_save_unarchive_clears_date_and_batch(
    company_factory: "Callable[..., Company]",
) -> None:
    """Verify un-archiving a row clears both archive_date and archive_batch_id."""
    # Given an archived company
    company = await company_factory(is_archived=True)
    assert company.archive_batch_id is not None

    # When it is un-archived via save()
    company.is_archived = False
    await company.save()

    # Then both stamps are cleared
    refreshed = await Company.get(id=company.id)
    assert refreshed.archive_date is None
    assert refreshed.archive_batch_id is None
