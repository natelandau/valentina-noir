"""Database utilities."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from beanie import init_beanie
from pymongo import AsyncMongoClient, MongoClient
from pymongo.errors import ServerSelectionTimeoutError

from vapi.config import settings
from vapi.db.models import init_beanie_models

if TYPE_CHECKING:
    from pymongo.asynchronous.database import AsyncDatabase

logger = logging.getLogger("vapi")


__all__ = ("init_database", "setup_database", "test_db_connection")


async def setup_database() -> AsyncMongoClient:
    """Setup the database."""
    while not test_db_connection():
        print("DB: Connection failed. Retrying...")  # noqa: T201
        await asyncio.sleep(1)
    client = await init_database()
    logger.info("Database setup complete", extra={"component": "database"})
    return client


def test_db_connection() -> bool:  # pragma: no cover
    """Test the database connection using pymongo.

    This function attempts to establish a connection to the MongoDB database
    using the configuration specified in ValentinaConfig. It uses a short
    timeout to quickly determine if the connection can be established.

    Returns:
        bool: True if the connection is successful, False otherwise.
    """
    msg = f"Testing connection to {settings.mongo.uri}..."
    logger.debug(msg, extra={"component": "database"})

    try:
        client: MongoClient = MongoClient(settings.mongo.uri, serverSelectionTimeoutMS=1800)
        client.server_info()
        logger.debug("Connection successful", extra={"component": "database"})
        client.close()
    except ServerSelectionTimeoutError:
        client.close()
        return False
    else:
        return True


async def init_database(
    client: AsyncMongoClient | None = None,
    database: AsyncDatabase | None = None,
) -> AsyncMongoClient:
    """Initialize the MongoDB database connection and configure Beanie ODM for document models.

    Connect to MongoDB using the provided client or create a new one with default configuration. Set up Beanie ODM with the application's document models for object-document mapping. Use an existing database instance or select one from the client based on configuration.

    Args:
        client (AsyncMongoClient | None): The existing database client to use. If None, create a new client with default settings. Defaults to None.
        database (AsyncDatabase | None): Existing database instance to use. If None, select database from client using configured name. Defaults to None.

    Returns:
        AsyncMongoClient: The initialized database client.
    """  # Create Motor client
    if not client:
        client = AsyncMongoClient(
            f"{settings.mongo.uri}", tz_aware=True, serverSelectionTimeoutMS=1800
        )

    # Initialize beanie with the Sample document class and a database
    await init_beanie(
        database=database if database is not None else client[settings.mongo.database_name],
        document_models=init_beanie_models,
    )
    logger.debug(
        "Models initialized",
        extra={
            "component": "database",
            "database_name": settings.mongo.database_name,
            "models": [model.__name__ for model in init_beanie_models],
        },
    )
    return client
