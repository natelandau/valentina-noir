"""New database connection for the migration script."""

import logging

from pymongo import AsyncMongoClient

from vapi.config import settings
from vapi.lib.database import init_database

logger = logging.getLogger("migrate")


async def connect_new_db() -> AsyncMongoClient:
    """Connect to the new Valentina Noir database and initialize Beanie.

    Returns:
        The initialized AsyncMongoClient.
    """
    client = await init_database()
    logger.info(
        "Connected to new database: %s",
        settings.mongo.database_name,
    )
    return client
