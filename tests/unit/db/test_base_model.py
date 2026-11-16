"""Tests for BaseModel archive-stamp and primary-key invariants."""

from typing import TYPE_CHECKING

import pytest

from vapi.db.sql_models.base import new_uuid
from vapi.db.sql_models.company import Company
from vapi.utils.time import time_now

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


async def test_partial_save_writes_archive_stamps_and_date_modified(
    company_factory: "Callable[..., Company]",
) -> None:
    """Verify a save naming only is_archived also writes the archive stamps and date_modified."""
    # Given an active company
    company = await company_factory(is_archived=False)
    original_modified = company.date_modified

    # When it is archived with a partial save that names only the archive flag
    company.is_archived = True
    await company.save(update_fields=["is_archived"])

    # Then the stored row carries both stamps and a new modification time
    stored = await Company.get(id=company.id)
    assert stored.is_archived is True
    assert stored.archive_date is not None
    assert stored.archive_batch_id is not None
    assert stored.date_modified > original_modified


async def test_stale_full_save_keeps_concurrent_archive(
    company_factory: "Callable[..., Company]",
) -> None:
    """Verify a full-row save of a row archived after load keeps the archive and its batch."""
    # Given a company loaded while active, then archived by a bulk cascade UPDATE
    company = await company_factory(is_archived=False)
    stale = await Company.get(id=company.id)
    batch_id = new_uuid()
    await Company.filter(id=company.id).update(
        is_archived=True, archive_date=time_now(), archive_batch_id=batch_id
    )

    # When the stale instance is edited and saved without update_fields
    stale.name = "edited name"
    await stale.save()

    # Then the edit lands but the row stays archived in the cascade batch
    row = await Company.get(id=company.id)
    assert row.name == "edited name"
    assert row.is_archived is True
    assert row.archive_batch_id == batch_id


async def test_full_save_writes_archive_changed_in_memory(
    company_factory: "Callable[..., Company]",
) -> None:
    """Verify a full-row save still writes an archive or restore set on the instance."""
    # Given a loaded active company
    company = await company_factory(is_archived=False)
    loaded = await Company.get(id=company.id)

    # When it is archived in memory and saved
    loaded.is_archived = True
    await loaded.save()

    # Then it is archived with stamps
    row = await Company.get(id=company.id)
    assert row.is_archived is True
    assert row.archive_batch_id is not None

    # When the same instance is restored in memory and saved again
    loaded.is_archived = False
    await loaded.save()

    # Then it is active with cleared stamps
    row = await Company.get(id=company.id)
    assert row.is_archived is False
    assert row.archive_batch_id is None
    assert row.archive_date is None
