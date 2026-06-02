"""Tests for BaseModel archive-stamp invariants."""

from typing import TYPE_CHECKING

import pytest

from vapi.db.sql_models.company import Company

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


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
