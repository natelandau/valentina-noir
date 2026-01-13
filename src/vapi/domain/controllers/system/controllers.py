"""System health controllers."""

from __future__ import annotations

import logging

from litestar import Controller, MediaType, get
from litestar.response import Response
from redis import RedisError

from vapi.config import settings
from vapi.domain import urls
from vapi.lib.database import test_db_connection
from vapi.openapi.tags import APITags

from . import dto

logger = logging.getLogger("vapi")


class SystemController(Controller):
    """System health controller."""

    tags = [APITags.SYSTEM.name]

    @get(
        path=urls.System.HEALTH,
        operation_id="checkSystemHealth",
        media_type=MediaType.JSON,
        cache=False,
        summary="Check system health",
        description="Verify the API and its dependencies are operational. Returns database and cache connectivity status. No authentication required.",
        exclude_from_auth=True,
    )
    async def check_system_health(self) -> Response[dto.SystemHealth]:
        """Check database available and returns app config info."""
        db_status = "online" if test_db_connection() else "offline"

        try:
            cache_ping = await settings.redis.get_client().ping()
        except RedisError:  # pragma: no cover
            cache_ping = False
        cache_status = "online" if cache_ping else "offline"
        healthy = cache_ping and db_status == "online"
        if healthy:
            logger.debug(
                "System Health Check",
                extra={
                    "database_status": db_status,
                    "cache_status": cache_status,
                    "controller": "system",
                },
            )
        else:
            logger.warning(  # pragma: no cover
                "System Health Check",
                extra={
                    "database_status": db_status,
                    "cache_status": cache_status,
                    "controller": "system",
                },
            )

        return Response(
            content=dto.SystemHealth(database_status=db_status, cache_status=cache_status),  # type: ignore [arg-type]
            status_code=200 if db_status == "online" and cache_ping else 500,
            media_type=MediaType.JSON,
        )
