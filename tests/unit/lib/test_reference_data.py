"""Test reference-data staleness detection."""

import logging

import pytest

from tests.fixtures import rolled_back_transaction
from vapi.cli.seed import seed_async
from vapi.db.sql_models.reference_data import ReferenceDataSeed
from vapi.lib import reference_data
from vapi.lib.reference_data import (
    reference_data_fingerprint,
    reference_data_is_current,
    warn_if_reference_data_stale,
)

pytestmark = pytest.mark.anyio


def test_fingerprint_changes_when_a_fixture_changes(tmp_path, mocker) -> None:
    """Verify editing a fixture file changes the fingerprint."""
    # Given a fixtures directory with one file
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    fixture = fixtures / "traits.json"
    fixture.write_text("[]")
    mocker.patch.object(reference_data, "FIXTURES_PATH", fixtures)
    before = reference_data_fingerprint()

    # When the fixture changes
    fixture.write_text('[{"name": "Willpower"}]')

    # Then the fingerprint differs
    assert reference_data_fingerprint() != before


def test_fingerprint_changes_when_a_migration_is_added(tmp_path, mocker) -> None:
    """Verify adding a migration changes the fingerprint even when fixtures are unchanged."""
    # Given a migrations directory with one migration
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_initial.py").write_text("")
    mocker.patch.object(reference_data, "MIGRATIONS_PATH", migrations)
    before = reference_data_fingerprint()

    # When a new migration is added
    (migrations / "0002_add_reference_column.py").write_text("")

    # Then the fingerprint differs
    assert reference_data_fingerprint() != before


async def test_reference_data_is_current_after_seed() -> None:
    """Verify a completed seed records a fingerprint that matches this build."""
    results: dict[str, object] = {}

    async def scenario() -> None:
        # Given a seed has run against this build
        await seed_async()
        # When checking freshness
        results["current"] = await reference_data_is_current()
        results["records"] = await ReferenceDataSeed.all().count()

    async with rolled_back_transaction():
        await scenario()

    # Then the reference data is current and recorded once
    assert results == {"current": True, "records": 1}


@pytest.mark.parametrize("record_fingerprint", [None, "0" * 64])
async def test_warn_if_reference_data_stale_logs_error(caplog, record_fingerprint) -> None:
    """Verify startup logs an error when no seed was recorded or it ran against another build."""
    results: dict[str, object] = {}

    async def scenario() -> None:
        # Given no seed record, or one from a different build
        await ReferenceDataSeed.all().delete()
        if record_fingerprint:
            await ReferenceDataSeed.create(fingerprint=record_fingerprint)
        # When the startup check runs
        with caplog.at_level(logging.ERROR, logger="vapi"):
            await warn_if_reference_data_stale()
        results["current"] = await reference_data_is_current()

    async with rolled_back_transaction():
        await scenario()

    # Then it reports stale reference data
    assert results["current"] is False
    assert "Reference data is out of date" in caplog.text


async def test_warn_if_reference_data_stale_quiet_when_current(caplog) -> None:
    """Verify startup logs nothing when the reference data matches this build."""

    async def scenario() -> None:
        # Given a seed recorded for this build
        await ReferenceDataSeed.all().delete()
        await ReferenceDataSeed.create(fingerprint=reference_data_fingerprint())
        # When the startup check runs
        with caplog.at_level(logging.ERROR, logger="vapi"):
            await warn_if_reference_data_stale()

    async with rolled_back_transaction():
        await scenario()

    # Then nothing is logged
    assert "Reference data" not in caplog.text
