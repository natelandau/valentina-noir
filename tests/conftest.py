"""Fixtures for the tests."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import asyncpg
import asyncpg.exceptions
import pytest
from pymongo import AsyncMongoClient
from redis.asyncio import Redis
from tortoise import Tortoise

from vapi.cli.bootstrap import bootstrap_async, pg_bootstrap_async
from vapi.config import settings
from vapi.db.models import (
    AuditLog,
    Campaign,
    CampaignBook,
    CampaignChapter,
    Character,
    CharacterInventory,
    CharacterTrait,
    Company,
    Developer,
    DiceRoll,
    DictionaryTerm,
    Note,
    QuickRoll,
    S3Asset,
    Trait,
    User,
)
from vapi.lib.database import init_database
from vapi.lib.postgres_database import tortoise_config

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

    from beanie import PydanticObjectId
    from httpx import AsyncClient
    from pytest_databases.docker.mongodb import MongoDBService
    from pytest_databases.docker.postgres import PostgresService
    from pytest_databases.docker.redis import RedisService


pytest_plugins = (
    "pytest_databases.docker.redis",
    "pytest_databases.docker.mongodb",
    "pytest_databases.docker.postgres",
    "tests.fixtures",
    "tests.fixture_models",
    "tests.pg_fixture_models",
    "tests.mocks",
)
# Set anyio as the default async backend for all tests
pytestmark = pytest.mark.anyio

TEST_DATABASE_NAME = "vapi-pytest"
TEST_MONGO_URI = "mongodb://localhost:27017"


@pytest.fixture(scope="session", autouse=True)
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def patch_settings():
    """Clear cached config that may have been created before test env vars were applied."""
    try:
        from vapi.config.oauth import get_discord_oauth_client

        get_discord_oauth_client.cache_clear()
    except Exception:  # noqa: BLE001, S110
        pass


_CLEANUP_MODELS = [
    AuditLog,
    Campaign,
    CampaignBook,
    CampaignChapter,
    Character,
    CharacterInventory,
    CharacterTrait,
    Company,
    Developer,
    DiceRoll,
    DictionaryTerm,
    Note,
    QuickRoll,
    User,
    S3Asset,
    Trait,
]


async def _cleanup_non_constant_db_data(
    base_company_id: PydanticObjectId | None = None,
    base_user_id: PydanticObjectId | None = None,
    base_campaign_id: PydanticObjectId | None = None,
    base_character_id: PydanticObjectId | None = None,
    base_campaign_book_id: PydanticObjectId | None = None,
    base_campaign_chapter_id: PydanticObjectId | None = None,
) -> None:
    """Delete all non-constant data from the database.

    Constant data (e.g. built-in Traits) is preserved; custom traits are removed.
    Base fixtures are preserved by ID so they don't need to be recreated each test.
    """
    preserve_by_id: dict[type, PydanticObjectId | None] = {
        Company: base_company_id,
        User: base_user_id,
        Campaign: base_campaign_id,
        Character: base_character_id,
        CampaignBook: base_campaign_book_id,
        CampaignChapter: base_campaign_chapter_id,
    }

    for model in _CLEANUP_MODELS:
        exclude_id = preserve_by_id.get(model)
        if exclude_id:
            await model.find(model.id != exclude_id).delete_many()
        elif model is Trait:
            await model.find(Trait.is_custom == True).delete_many()
        else:
            await model.delete_all()


@pytest.fixture(autouse=True)
async def cleanup_database(
    request: pytest.FixtureRequest,
    base_company: Company,
    base_user: User,
    base_campaign: Campaign,
    base_character: Character,
    base_campaign_book: CampaignBook,
    base_campaign_chapter: CampaignChapter,
) -> AsyncGenerator[None]:
    """Cleanup non-constant database data around each test.

    Before: runs full cleanup only when the test is marked with ``@pytest.mark.clean_db``.
    After: always runs full cleanup so tests cannot leak data to subsequent tests.
    """
    if "clean_db" in request.keywords:
        await _cleanup_non_constant_db_data(
            base_company_id=base_company.id,
            base_user_id=base_user.id,
            base_campaign_id=base_campaign.id,
            base_character_id=base_character.id,
            base_campaign_book_id=base_campaign_book.id,
            base_campaign_chapter_id=base_campaign_chapter.id,
        )

    yield

    await _cleanup_non_constant_db_data(
        base_company_id=base_company.id,
        base_user_id=base_user.id,
        base_campaign_id=base_campaign.id,
        base_character_id=base_character.id,
        base_campaign_book_id=base_campaign_book.id,
        base_campaign_chapter_id=base_campaign_chapter.id,
    )


@pytest.fixture(scope="session")
def worker_id(request):
    """Get xdist worker ID."""
    if hasattr(request.config, "workerinput"):
        return request.config.workerinput["workerid"]
    return "master"


@pytest.fixture(autouse=True, scope="session")
async def init_test_database(
    mongodb_service: MongoDBService,
    request,
    worker_id: str,
) -> AsyncMongoClient:
    """Initialize the database."""
    settings.mongo.uri = f"mongodb://{mongodb_service.username}:{mongodb_service.password}@{mongodb_service.host}:{mongodb_service.port}"

    db_name = f"vapi-pytest-{worker_id}" if worker_id != "master" else "vapi-pytest"
    settings.mongo.database_name = db_name

    client = AsyncMongoClient(settings.mongo.uri, tz_aware=True, serverSelectionTimeoutMS=1800)

    # Initialize beanie with the Sample document class and a database
    await init_database(
        client=client,
        database=client[db_name],
    )

    # Bootstrap the database with constants
    await bootstrap_async(do_setup_database=False)

    yield client
    await client.drop_database(db_name)
    await client.close()


@pytest.fixture(autouse=True, scope="session")
async def init_test_postgres(
    postgres_service: PostgresService,
    worker_id: str,
) -> AsyncGenerator[None]:
    """Initialize TortoiseORM against the test PostgreSQL container."""
    db_name = f"vapi_pytest_{worker_id}" if worker_id != "master" else "vapi_pytest"

    # Update settings to point at the test container
    settings.postgres.host = postgres_service.host
    settings.postgres.port = postgres_service.port
    settings.postgres.user = postgres_service.user
    settings.postgres.password = postgres_service.password
    settings.postgres.database = db_name

    # Use asyncpg directly to create the test DB, avoiding Tortoise admin connection
    admin_conn = await asyncpg.connect(
        host=postgres_service.host,
        port=postgres_service.port,
        user=postgres_service.user,
        password=postgres_service.password,
        database="postgres",
    )
    with contextlib.suppress(asyncpg.exceptions.DuplicateDatabaseError):
        await admin_conn.execute(f"CREATE DATABASE {db_name}")
    await admin_conn.close()

    # Now connect to the actual test database
    config = tortoise_config()
    await Tortoise.init(config=config)
    await Tortoise.generate_schemas(safe=True)

    # Bootstrap PostgreSQL with constants (mirrors MongoDB bootstrap above)
    await pg_bootstrap_async()

    yield

    await Tortoise.close_connections()


# Tables that hold non-constant data created by tests. Truncated after each test
# to prevent data leaks. Constant tables (char_sheet_section, trait_category, etc.)
# are seeded once at session scope and preserved.
# Non-constant PG tables that tests may write to. Quoted to handle reserved words
# like "user". Constant tables (char_sheet_section, trait_category, trait,
# vampire_clan, werewolf_auspice, werewolf_tribe, character_concept,
# dictionary_term, and their M2M junction tables) are seeded once at session scope
# and excluded from cleanup.
#
# IMPORTANT: Only these tables are listed - not constant tables. We deliberately
# avoid CASCADE because it would wipe constant tables that have nullable FK
# relationships to these tables (e.g., character_concept.company_id). Instead,
# we list only the tables that tests actually write to, and TRUNCATE them together
# in a single statement (PostgreSQL handles FK ordering within a multi-table TRUNCATE).
_PG_CLEANUP_TABLES = [
    '"audit_log"',
    '"chargen_session_characters"',
    '"chargen_session"',
    '"note"',
    '"s3_asset"',
    '"dice_roll"',
    '"quick_roll"',
    '"character_trait"',
    '"character_inventory"',
    '"specialty"',
    '"vampire_attributes"',
    '"werewolf_attributes"',
    '"mage_attributes"',
    '"hunter_attributes"',
    '"character"',
    '"campaign_chapter"',
    '"campaign_book"',
    '"campaign"',
    '"campaign_experience"',
    '"company_settings"',
    '"developer_company_permission"',
    '"developer"',
    '"user"',
    '"company"',
]


async def _cleanup_non_constant_pg_data() -> None:
    """Delete all non-constant data from PostgreSQL tables.

    Constant data (traits, sections, clans, etc.) is preserved. Uses DELETE (not
    TRUNCATE) to avoid CASCADE side effects on constant tables that have nullable FK
    relationships to these tables. Tables are ordered children-first so FK constraints
    are satisfied.
    """
    conn = Tortoise.get_connection("default")
    for table in _PG_CLEANUP_TABLES:
        await conn.execute_query(f"DELETE FROM {table}")  # noqa: S608


@pytest.fixture(autouse=True)
async def cleanup_pg_database() -> AsyncGenerator[None]:
    """Cleanup non-constant PostgreSQL data after each test.

    Mirrors the MongoDB cleanup_database fixture pattern - truncates all non-constant
    tables after each test to prevent data leaks between tests.
    """
    yield
    await _cleanup_non_constant_pg_data()


@pytest.fixture(name="redis", autouse=True)
async def fx_redis(redis_service: RedisService) -> AsyncGenerator[Redis]:
    """Redis instance for testing."""
    redis_client = Redis(host=redis_service.host, port=redis_service.port)
    yield redis_client
    await redis_client.aclose()


@pytest.fixture(name="client")
async def fx_client(redis: Redis, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    """Create an async HTTP client that connects to the app."""
    from httpx import ASGITransport, AsyncClient
    from litestar_saq.cli import get_saq_plugin

    from vapi.asgi import create_app
    from vapi.config.base import RedisSettings
    from vapi.lib.database import setup_database
    from vapi.server.core import ApplicationCore
    from vapi.server.tortoise_plugin import _shutdown, _startup

    app = create_app()
    app.on_startup = [h for h in app.on_startup if h not in {setup_database, _startup}]
    app.on_shutdown = [h for h in app.on_shutdown if h is not _shutdown]

    cache_config = app.response_cache_config
    assert cache_config is not None

    saq_plugin = get_saq_plugin(app) if settings.saq.enabled else None
    app_plugin = app.plugins.get(ApplicationCore)
    monkeypatch.setattr(app_plugin, "redis", redis)
    monkeypatch.setattr(app.stores.get(cache_config.store), "_redis", redis)
    if saq_plugin and saq_plugin._config.queue_instances is not None:
        for queue in saq_plugin._config.queue_instances.values():
            monkeypatch.setattr(queue, "redis", redis)

    # Patch settings.redis.get_client to return our test Redis instance
    monkeypatch.setattr(RedisSettings, "get_client", lambda self: redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
