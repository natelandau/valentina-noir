"""New database connection for the migration script."""

import logging

from tortoise import Tortoise

from vapi.lib.database import init_tortoise

logger = logging.getLogger("migrate")


async def connect_new_db() -> None:
    """Initialize TortoiseORM for the new PostgreSQL database."""
    await init_tortoise()
    logger.info("Connected to new PostgreSQL database")


async def close_new_db() -> None:
    """Close all TortoiseORM connections."""
    await Tortoise.close_connections()
