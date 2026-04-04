"""TortoiseORM lifecycle for Litestar."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from tortoise import Tortoise

from vapi.lib.database import tortoise_config

logger = logging.getLogger("vapi")


@asynccontextmanager
async def tortoise_lifespan(_app: object) -> AsyncGenerator[None]:
    """Manage TortoiseORM lifecycle as a Litestar lifespan context manager.

    Using a lifespan context manager instead of on_startup/on_shutdown ensures
    the TortoiseContext (contextvar) remains active for all request handling,
    since Tortoise v1.x scopes its connections via contextvars.
    """
    await Tortoise.init(config=tortoise_config(), _enable_global_fallback=True)
    await Tortoise.generate_schemas(safe=True)
    logger.info("PostgreSQL database initialized", extra={"component": "database"})
    try:
        yield
    finally:
        await Tortoise.close_connections()
        logger.info("PostgreSQL connections closed", extra={"component": "database"})
