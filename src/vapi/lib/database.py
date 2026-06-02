"""Database configuration and initialization.

PostgreSQL via TortoiseORM is the primary database.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import asyncpg

from vapi.config import settings

logger = logging.getLogger("vapi")


async def init_tortoise() -> None:
    """Initialize TortoiseORM for use outside the Litestar application lifecycle.

    Use this when Tortoise needs to be initialized standalone, such as in
    background tasks or CLI commands that run without a running Litestar app.
    """
    from tortoise import Tortoise

    await Tortoise.init(config=tortoise_config(), _enable_global_fallback=True)


def tortoise_config() -> dict[str, Any]:
    """Build the TortoiseORM configuration dict from application settings.

    Returns a config dict suitable for ``Tortoise.init(config=...)``. Uses the
    credentials-based format so individual settings fields map directly without
    URL construction.
    """
    return {
        "connections": {
            "default": {
                "engine": "tortoise.backends.asyncpg",
                "credentials": {
                    "host": settings.postgres.host,
                    "port": settings.postgres.port,
                    "user": settings.postgres.user,
                    "password": settings.postgres.password,
                    "database": settings.postgres.database,
                },
            },
        },
        "apps": {
            "models": {
                "models": ["vapi.db.sql_models"],
                "default_connection": "default",
                "migrations": "vapi.db.migrations",
            },
        },
        "use_tz": True,
    }


# SQL that installs the archive-stamp enforcement trigger on every BaseModel
# table. The migration (0010) carries the same SQL for incremental upgrades of
# existing databases; this constant is the source of truth for fresh-schema
# paths (Tortoise.generate_schemas) which bypass migrations entirely. Keep the
# two in sync.
_ARCHIVE_TRIGGER_FUNCTION_SQL = (
    "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
    "CREATE OR REPLACE FUNCTION enforce_archive_stamps() "
    "RETURNS trigger AS $$ BEGIN "
    "IF NEW.is_archived THEN "
    "IF NEW.archive_date IS NULL THEN NEW.archive_date := now(); END IF; "
    "IF NEW.archive_batch_id IS NULL THEN "
    "NEW.archive_batch_id := gen_random_uuid(); END IF; "
    "ELSE NEW.archive_date := NULL; NEW.archive_batch_id := NULL; "
    "END IF; RETURN NEW; END; $$ LANGUAGE plpgsql;"
)

_ARCHIVE_TRIGGER_ATTACH_SQL = (
    "DO $$ DECLARE tbl text; BEGIN "
    "FOR tbl IN SELECT table_name FROM information_schema.columns "
    "WHERE table_schema = 'public' AND column_name = 'archive_batch_id' "
    "LOOP "
    "EXECUTE format("
    "'DROP TRIGGER IF EXISTS trg_enforce_archive_stamps ON %I', tbl); "
    "EXECUTE format("
    "'CREATE TRIGGER trg_enforce_archive_stamps "
    "BEFORE INSERT OR UPDATE ON %I FOR EACH ROW "
    "EXECUTE FUNCTION enforce_archive_stamps()', tbl); "
    "END LOOP; END $$;"
)


async def install_archive_stamp_trigger() -> None:
    """Install the archive-stamp enforcement trigger on every archivable table.

    Tortoise's ``generate_schemas`` creates tables straight from the models and
    never runs migration RunSQL, so fresh databases (tests, initial production
    setup) would otherwise lack the DB-level backstop that guarantees archived
    rows always carry both ``archive_date`` and ``archive_batch_id``. Call this
    immediately after ``generate_schemas`` to close that gap. Idempotent.
    """
    from tortoise import Tortoise

    conn = Tortoise.get_connection("default")
    await conn.execute_script(_ARCHIVE_TRIGGER_FUNCTION_SQL)
    await conn.execute_script(_ARCHIVE_TRIGGER_ATTACH_SQL)


def __getattr__(name: str) -> dict[str, Any]:
    """Lazy module-level attribute for the `tortoise` CLI (e.g. `tortoise -c vapi.lib.database.TORTOISE_ORM`)."""
    if name == "TORTOISE_ORM":
        return tortoise_config()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def pg_subprocess_env() -> dict[str, str]:
    """Return the environment for invoking ``pg_dump`` / ``pg_restore`` subprocesses.

    Inherits the parent environment so the subprocess can find PATH, locale
    data, and shared libs, then overlays ``PGPASSWORD`` so libpq can
    authenticate without needing a ``.pgpass`` file.
    """
    return {**os.environ, "PGPASSWORD": settings.postgres.password}


async def drop_and_recreate_database() -> None:
    """Drop and recreate the configured PostgreSQL database.

    Connect to the ``postgres`` maintenance database to execute DROP/CREATE,
    since you cannot drop a database while connected to it. Terminate any
    lingering connections before the DROP so it does not block.
    """
    pg = settings.postgres
    conn = await asyncpg.connect(
        host=pg.host,
        port=pg.port,
        user=pg.user,
        password=pg.password,
        database="postgres",
    )
    try:
        # Terminate existing connections before DROP to prevent blocking
        terminate_sql = f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{pg.database}' AND pid <> pg_backend_pid()"  # noqa: S608
        await conn.execute(terminate_sql)
        await conn.execute(f'DROP DATABASE IF EXISTS "{pg.database}"')
        await conn.execute(f'CREATE DATABASE "{pg.database}" OWNER {pg.user}')
    finally:
        await conn.close()


async def test_db_connection() -> bool:  # pragma: no cover
    """Test the PostgreSQL database connection.

    Use a short timeout to quickly determine if the connection can be established.

    Returns:
        True if the connection is successful, False otherwise.
    """
    import asyncio

    try:
        conn = await asyncio.wait_for(
            asyncpg.connect(
                host=settings.postgres.host,
                port=settings.postgres.port,
                user=settings.postgres.user,
                password=settings.postgres.password,
                database=settings.postgres.database,
            ),
            timeout=2.0,
        )
        await conn.close()
    except Exception:  # noqa: BLE001
        return False
    else:
        return True
