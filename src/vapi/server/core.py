"""Application core configuration plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from click import Group  # noqa: TC002
from litestar.plugins import CLIPluginProtocol, InitPluginProtocol

from vapi.config import settings
from vapi.lib.database import setup_database

from .stores import RedisStore

if TYPE_CHECKING:
    from litestar.config.app import AppConfig
    from litestar.types import HTTPScope
    from redis.asyncio import Redis


T = TypeVar("T")


class ApplicationCore(InitPluginProtocol, CLIPluginProtocol):
    """Application core configuration plugin.

    This class is responsible for configuring the main Litestar application with our routes, guards, and various plugins
    """

    __slots__ = ("app_slug", "redis")
    redis: Redis
    app_slug: str

    def on_cli_init(self, cli: Group) -> None:
        """Initialize CLI by adding custom commands."""
        from vapi.cli import bootstrap, developer_group, development_group

        cli.add_command(bootstrap)
        cli.add_command(developer_group)
        cli.add_command(development_group)

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Configure application for use with SQLAlchemy.

        Args:
            app_config: The app config.
        """
        from beanie import PydanticObjectId
        from litestar.config.cors import CORSConfig
        from litestar.config.response_cache import ResponseCacheConfig
        from litestar.exceptions import HTTPException
        from litestar.stores.registry import StoreRegistry

        from vapi.domain import route_handlers
        from vapi.lib.exceptions import (
            HTTPError,
            http_error_to_http_response,
            litestar_http_exc_to_http_response,
        )
        from vapi.lib.log_config import get_logging_config, middleware_logging_config
        from vapi.lib.stores import response_cache_key_builder
        from vapi.middleware.authentication import auth_mw
        from vapi.middleware.cache_control_headers import cache_control_middleware
        from vapi.middleware.idempotency import idempotency_middleware
        from vapi.middleware.rate_limit import rate_limit_middleware
        from vapi.openapi.config import create_openapi_config
        from vapi.server import plugins
        from vapi.server.custom_types import DecodePydanticObjectId

        self.redis = settings.redis.get_client()
        self.app_slug = settings.slug
        app_config.debug = settings.debug

        app_config.openapi_config = create_openapi_config()

        app_config.plugins.extend([plugins.granian, plugins.oauth])

        app_config.type_encoders = {PydanticObjectId: str}
        app_config.type_decoders = [
            (
                DecodePydanticObjectId.is_pydantic_object_id,
                DecodePydanticObjectId.decode,
            )
        ]

        app_config.route_handlers.extend(route_handlers)
        app_config.logging_config = get_logging_config()

        app_config.middleware.extend(
            [
                auth_mw,
                rate_limit_middleware,
                idempotency_middleware,
                cache_control_middleware,
                middleware_logging_config.middleware,
            ]
        )

        if settings.cors.enabled:
            app_config.cors_config = CORSConfig(
                allow_origins=settings.cors.allowed_origins,
                allow_origin_regex=settings.cors.allow_origin_regex,
            )

        app_config.exception_handlers = {
            HTTPError: http_error_to_http_response,
            HTTPException: litestar_http_exc_to_http_response,
        }

        app_config.response_cache_config = ResponseCacheConfig(
            default_expiration=settings.stores.ttl,
            key_builder=response_cache_key_builder,
            store=settings.stores.response_cache_key,
            cache_response_filter=self.custom_cache_response_filter,
        )
        app_config.stores = StoreRegistry(default_factory=self.redis_store_factory)
        app_config.on_startup.append(setup_database)
        app_config.on_shutdown.append(self.redis.aclose)

        app_config.listeners.extend([])

        return app_config

    def redis_store_factory(self, name: str) -> RedisStore:
        """Redis store factory."""
        return RedisStore(self.redis, namespace=f"{settings.slug}:{name}")

    def custom_cache_response_filter(self, scope: HTTPScope, status_code: int) -> bool:
        """Custom cache response filter."""
        # Don't cache POST, PUT, PATCH, or DELETE requests
        if scope.get("method") in {"POST", "PUT", "PATCH", "DELETE"}:
            return False

        # Cache only 2xx responses
        return 200 <= status_code < 300  # noqa: PLR2004
