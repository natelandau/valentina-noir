"""Detect reference data that is out of date with the running build.

The seed records a fingerprint of the fixture files and the migration set it ran against.
A build whose fingerprint differs either ships fixture changes the database never received,
or ships migrations (which may add reference-data columns that only the seed fills in) that
ran without a seed afterward.
"""

import hashlib
import logging

from tortoise.exceptions import BaseORMException

from vapi.constants import PROJECT_ROOT_PATH
from vapi.db.sql_models.reference_data import ReferenceDataSeed

logger = logging.getLogger("vapi")

FIXTURES_PATH = PROJECT_ROOT_PATH / "src/vapi/db/fixtures"
MIGRATIONS_PATH = PROJECT_ROOT_PATH / "src/vapi/db/migrations"


def reference_data_fingerprint() -> str:
    """Hash the fixture files and migration names that determine what the seed writes.

    Returns:
        str: A hex SHA-256 digest that changes whenever a fixture or the migration set changes.
    """
    digest = hashlib.sha256()
    for migration in sorted(MIGRATIONS_PATH.glob("[0-9][0-9][0-9][0-9]_*.py")):
        digest.update(migration.stem.encode())
        digest.update(b"\0")
    for fixture in sorted(p for p in FIXTURES_PATH.rglob("*") if p.is_file()):
        digest.update(fixture.relative_to(FIXTURES_PATH).as_posix().encode())
        digest.update(b"\0")
        digest.update(fixture.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


async def record_reference_data_seed() -> None:
    """Record that the reference data now matches this build. Call at the end of a seed."""
    await ReferenceDataSeed.all().delete()
    await ReferenceDataSeed.create(fingerprint=reference_data_fingerprint())


async def reference_data_is_current() -> bool:
    """Check whether the last seed ran against this build's fixtures and migrations.

    Returns:
        bool: True when the recorded fingerprint matches this build, False when it differs
            or no seed has been recorded.
    """
    record = await ReferenceDataSeed.all().order_by("-date_created").first()
    return record is not None and record.fingerprint == reference_data_fingerprint()


async def warn_if_reference_data_stale() -> None:
    """Log an error at startup when reference data is out of date with this build.

    Only log, never refuse to start: a stale seed degrades reference fields (for example,
    traits without trackers) but leaves the rest of the API working.
    """
    try:
        current = await reference_data_is_current()
    except BaseORMException:
        # The seed-record table is missing, so migrations have not been applied either
        logger.exception(
            "Could not read the reference-data seed record. Run `app migrate`.",
            extra={"component": "database"},
        )
        return

    if not current:
        logger.error(
            "Reference data is out of date with this build. Run `app migrate`, which "
            "applies pending migrations and re-seeds reference data.",
            extra={"component": "database"},
        )
