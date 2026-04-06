"""Database configuration and initialization.

PostgreSQL via TortoiseORM is the primary database.
"""

from __future__ import annotations

import logging
from typing import Any

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
    }


def __getattr__(name: str) -> dict[str, Any]:
    """Lazy module-level attribute for the `tortoise` CLI (e.g. `tortoise -c vapi.lib.database.TORTOISE_ORM`)."""
    if name == "TORTOISE_ORM":
        return tortoise_config()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


async def test_db_connection() -> bool:  # pragma: no cover
    """Test the PostgreSQL database connection.

    Use a short timeout to quickly determine if the connection can be established.

    Returns:
        True if the connection is successful, False otherwise.
    """
    import asyncio

    import asyncpg

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
