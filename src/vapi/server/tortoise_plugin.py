"""TortoiseORM lifecycle plugin for Litestar."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from litestar.plugins import InitPluginProtocol
from tortoise import Tortoise

from vapi.lib.database import tortoise_config

if TYPE_CHECKING:
    from litestar.config.app import AppConfig

logger = logging.getLogger("vapi")


class TortoisePlugin(InitPluginProtocol):
    """Manage TortoiseORM startup and shutdown within the Litestar app lifecycle."""

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Register Tortoise startup and shutdown hooks.

        Args:
            app_config: The Litestar application configuration.
        """
        app_config.on_startup.append(_startup)
        app_config.on_shutdown.append(_shutdown)
        return app_config


async def _startup() -> None:
    """Initialize TortoiseORM and create any missing tables."""
    await Tortoise.init(config=tortoise_config())
    await Tortoise.generate_schemas(safe=True)
    logger.info("PostgreSQL database initialized", extra={"component": "database"})


async def _shutdown() -> None:
    """Close all TortoiseORM database connections."""
    await Tortoise.close_connections()
    logger.info("PostgreSQL connections closed", extra={"component": "database"})
