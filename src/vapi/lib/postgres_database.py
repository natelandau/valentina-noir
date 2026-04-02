"""PostgreSQL database configuration for TortoiseORM."""

from __future__ import annotations

from typing import Any

from vapi.config import settings


async def init_tortoise() -> None:
    """Initialize TortoiseORM for use outside the Litestar application lifecycle.

    Use this when Tortoise needs to be initialized standalone, such as in
    background tasks or CLI commands that run without a running Litestar app.
    """
    from tortoise import Tortoise

    await Tortoise.init(config=tortoise_config())


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
            },
        },
    }
