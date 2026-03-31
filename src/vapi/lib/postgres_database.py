"""PostgreSQL database configuration for TortoiseORM."""

from __future__ import annotations

from typing import Any

from vapi.config import settings


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
                "models": [],
                "default_connection": "default",
            },
        },
    }
