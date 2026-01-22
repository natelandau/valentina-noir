"""Fixtures for the tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from nclutils.pytest_fixtures import clean_stderr, debug  # noqa: F401
from pymongo import AsyncMongoClient
from redis.asyncio import Redis

from vapi.cli.bootstrap import bootstrap_async
from vapi.config import settings
from vapi.constants import LogLevel
from vapi.lib.database import init_database

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

    from beanie import PydanticObjectId
    from httpx import AsyncClient
    from pytest_databases.docker.mongodb import MongoDBService
    from pytest_databases.docker.redis import RedisService

    from vapi.db.models import (
        Campaign,
        CampaignBook,
        CampaignChapter,
        Character,
        Company,
        User,
    )


pytest_plugins = (
    "pytest_databases.docker.redis",
    "pytest_databases.docker.mongodb",
    "tests.fixtures",
    "tests.fixture_models",
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
    """Patch the settings to use the test mongo client."""
    settings.log.level = LogLevel.WARNING
    settings.log.file_path = None
    settings.log.request_log_fields = ["path", "method"]
    settings.log.asgi_server_level = LogLevel.WARNING
    settings.log.root_level = LogLevel.WARNING
    settings.log.log_exceptions = "debug"
    settings.log.time_in_console = False
    settings.debug = True
    settings.name = "vapi-pytest"
    settings.oauth.discord_client_id = "MOCK_CLIENT_ID"
    settings.oauth.discord_client_secret = "MOCK_CLIENT_SECRET"  # noqa: S105
    settings.rate_limit.encryption_key = "MOCK_AUTHENTICATION_ENCRYPTION_KEY"
    settings.authentication_encryption_key = "MOCK_AUTHENTICATION_ENCRYPTION_KEY"
    settings.server.host = "testserver"
    settings.aws.access_key_id = "MOCK_ACCESS_KEY_ID"
    settings.aws.secret_access_key = "MOCK_SECRET_ACCESS_KEY"  # noqa: S105
    settings.aws.s3_bucket_name = "MOCK_S3_BUCKET_NAME"
    settings.aws.cloudfront_origin_path = "MOCK_ORIGIN_PATH"
    settings.aws.cloudfront_url = "MOCK_URL"
    settings.saq.web_enabled = False
    settings.saq.processes = 1
    settings.saq.use_server_lifespan = True
    settings.saq.enabled = False
    settings.saq.admin_username = "test_admin"
    settings.saq.admin_password = "test_password"  # noqa: S105

    # Clear any stray instances of the lru_cache
    try:
        from vapi.config.oauth import get_discord_oauth_client

        get_discord_oauth_client.cache_clear()
    except Exception:  # noqa: BLE001, S110
        pass


async def _cleanup_non_constant_db_data(
    base_company_id: PydanticObjectId | None = None,
    base_user_id: PydanticObjectId | None = None,
    base_campaign_id: PydanticObjectId | None = None,
    base_character_id: PydanticObjectId | None = None,
    base_campaign_book_id: PydanticObjectId | None = None,
    base_campaign_chapter_id: PydanticObjectId | None = None,
) -> AsyncGenerator[None]:
    """Cleanup non-constant data from the database."""
    from vapi.db.models import (
        AuditLog,
        Campaign,
        CampaignBook,
        CampaignChapter,
        Character,
        CharacterInventory,
        CharacterTrait,
        Company,
        DiceRoll,
        DictionaryTerm,
        Note,
        QuickRoll,
        S3Asset,
        Trait,
        User,
    )

    for model in [
        AuditLog,
        Campaign,
        CampaignBook,
        CampaignChapter,
        Character,
        CharacterInventory,
        CharacterTrait,
        Company,
        DiceRoll,
        DictionaryTerm,
        Note,
        QuickRoll,
        User,
        S3Asset,
        Trait,
    ]:
        if model == Company and base_company_id:
            await model.find(Company.id != base_company_id).delete_many()
        elif model == User and base_user_id:
            await model.find(User.id != base_user_id).delete_many()
        elif model == Campaign and base_campaign_id:
            await model.find(Campaign.id != base_campaign_id).delete_many()
        elif model == Character and base_character_id:
            await model.find(Character.id != base_character_id).delete_many()
        elif model == CampaignBook and base_campaign_book_id:
            await model.find(CampaignBook.id != base_campaign_book_id).delete_many()
        elif model == CampaignChapter and base_campaign_chapter_id:
            await model.find(CampaignChapter.id != base_campaign_chapter_id).delete_many()
        elif model == Trait:
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
    """Cleanup the database before the test when '@pytest.mark.clean_db()' is called and clean up non-constant data from the database after the test unless '()' is called."""
    if "clean_db" in request.keywords:
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
    from vapi.server.core import ApplicationCore

    app = create_app()
    app.on_startup = [handler for handler in app.on_startup if handler.__name__ != "setup_database"]

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
