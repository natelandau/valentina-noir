"""Tests for the DB-level archive-stamp enforcement trigger."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from vapi.db.sql_models.company import Company

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


async def test_bulk_update_archive_gets_stamps_from_trigger(
    company_factory: "Callable[..., Company]",
) -> None:
    """Verify a bulk update(is_archived=True) with no stamps still gets them."""
    # Given an active company
    company = await company_factory(is_archived=False)

    # When archived via a bulk update that supplies NEITHER date nor batch id
    await Company.filter(id=company.id).update(is_archived=True)

    # Then the trigger has filled both stamps
    refreshed = await Company.get(id=company.id)
    assert refreshed.archive_date is not None
    assert refreshed.archive_batch_id is not None


async def test_bulk_update_unarchive_clears_stamps_via_trigger(
    company_factory: "Callable[..., Company]",
) -> None:
    """Verify a bulk update(is_archived=False) clears the stamps via the trigger."""
    # Given an archived company
    company = await company_factory(is_archived=True)

    # When un-archived via a bulk update that does not clear the stamps
    await Company.filter(id=company.id).update(is_archived=False)

    # Then the trigger has cleared both stamps
    refreshed = await Company.get(id=company.id)
    assert refreshed.archive_date is None
    assert refreshed.archive_batch_id is None


async def test_raw_insert_archived_gets_stamps_from_trigger() -> None:
    """Verify a raw-SQL INSERT of an archived row gets both stamps from the trigger."""
    # Given a row id and a raw INSERT that bypasses the ORM save() override
    # entirely, marking the row archived but supplying NEITHER archive stamp
    from tortoise import Tortoise

    company_id = uuid4()
    conn = Tortoise.get_connection("default")

    # When the row is inserted directly via SQL (the trigger's INSERT branch runs)
    await conn.execute_query(
        "INSERT INTO company "
        "(id, name, email, is_archived, date_created, date_modified, resources_modified_at) "
        "VALUES ($1, $2, $3, true, now(), now(), now())",
        [company_id, "Trigger Insert Co", "trigger@example.com"],
    )

    # Then the trigger populated both stamps even though the ORM was bypassed
    inserted = await Company.get(id=company_id)
    assert inserted.archive_date is not None
    assert inserted.archive_batch_id is not None
