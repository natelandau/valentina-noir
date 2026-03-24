"""Read-only access to the old Valentina database via Motor."""

import logging
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from scripts.migrate.config import get_old_settings

logger = logging.getLogger("migrate")


async def connect_old_db() -> tuple[AsyncMongoClient, AsyncDatabase]:
    """Connect to the old Valentina MongoDB database.

    Returns:
        Tuple of (client, database) for the old database.
    """
    old_settings = get_old_settings()
    client: AsyncMongoClient = AsyncMongoClient(old_settings.mongo_uri, tz_aware=True)
    db = client[old_settings.mongo_database_name]
    logger.info("Connected to old database: %s", old_settings.mongo_database_name)
    return client, db


async def read_guilds(db: AsyncDatabase) -> list[dict[str, Any]]:
    """Read all Guild documents from the old database.

    Args:
        db: The old database connection.

    Returns:
        List of guild documents as plain dicts.
    """
    return [doc async for doc in db["Guild"].find()]


async def read_users(db: AsyncDatabase) -> list[dict[str, Any]]:
    """Read all User documents from the old database.

    Args:
        db: The old database connection.

    Returns:
        List of user documents as plain dicts.
    """
    return [doc async for doc in db["User"].find()]


async def read_campaigns(db: AsyncDatabase, guild_id: int) -> list[dict[str, Any]]:
    """Read non-deleted Campaign documents for a specific guild.

    Args:
        db: The old database connection.
        guild_id: The guild ID to filter by.

    Returns:
        List of campaign documents as plain dicts.
    """
    return [
        doc async for doc in db["Campaign"].find({"guild": guild_id, "is_deleted": {"$ne": True}})
    ]


async def read_campaign_books(db: AsyncDatabase, campaign_id: str) -> list[dict[str, Any]]:
    """Read CampaignBook documents for a specific campaign.

    Args:
        db: The old database connection.
        campaign_id: The campaign ID string to filter by.

    Returns:
        List of campaign book documents as plain dicts.
    """
    return [doc async for doc in db["CampaignBook"].find({"campaign": campaign_id})]


async def read_campaign_chapters(db: AsyncDatabase, book_id: str) -> list[dict[str, Any]]:
    """Read CampaignBookChapter documents for a specific book.

    Args:
        db: The old database connection.
        book_id: The book ID string to filter by.

    Returns:
        List of chapter documents as plain dicts.
    """
    return [doc async for doc in db["CampaignBookChapter"].find({"book": book_id})]


async def read_characters(db: AsyncDatabase, guild_id: int) -> list[dict[str, Any]]:
    """Read Character documents for a specific guild.

    Args:
        db: The old database connection.
        guild_id: The guild ID to filter by.

    Returns:
        List of character documents as plain dicts.
    """
    return [doc async for doc in db["Character"].find({"guild": guild_id})]


async def read_character_traits(db: AsyncDatabase, character_id: str) -> list[dict[str, Any]]:
    """Read CharacterTrait documents for a specific character.

    Args:
        db: The old database connection.
        character_id: The character ID string to filter by.

    Returns:
        List of trait documents as plain dicts.
    """
    return [doc async for doc in db["CharacterTrait"].find({"character": character_id})]


async def read_inventory_items(db: AsyncDatabase, character_id: str) -> list[dict[str, Any]]:
    """Read InventoryItem documents for a specific character.

    Args:
        db: The old database connection.
        character_id: The character ID string to filter by.

    Returns:
        List of inventory item documents as plain dicts.
    """
    return [doc async for doc in db["InventoryItem"].find({"character": character_id})]


async def read_notes(db: AsyncDatabase, guild_id: int | None = None) -> list[dict[str, Any]]:
    """Read Note documents, optionally filtered by guild.

    Args:
        db: The old database connection.
        guild_id: Optional guild ID to filter by.

    Returns:
        List of note documents as plain dicts.
    """
    query: dict[str, Any] = {}
    if guild_id is not None:
        query["guild_id"] = guild_id
    return [doc async for doc in db["Note"].find(query)]


async def read_roll_statistics(db: AsyncDatabase, guild_id: int) -> list[dict[str, Any]]:
    """Read RollStatistic documents for a specific guild.

    Args:
        db: The old database connection.
        guild_id: The guild ID to filter by.

    Returns:
        List of roll statistic documents as plain dicts.
    """
    return [doc async for doc in db["RollStatistic"].find({"guild": guild_id})]
