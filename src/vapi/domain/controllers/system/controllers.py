"""System health controllers."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from litestar import Controller, MediaType, get
from litestar.response import Response
from redis import RedisError

from vapi.config import settings
from vapi.domain import urls
from vapi.lib.database import test_db_connection
from vapi.lib.uptime import APP_START_TIME
from vapi.openapi.tags import APITags
from vapi.utils.strings import format_uptime

from . import docs, dto

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
        description=docs.HEALTH_CHECK_DESCRIPTION,
    )
    async def check_system_health(self) -> Response[dto.SystemHealth]:
        """Check database available and returns app config info."""
        db_start = time.perf_counter()
        db_online = await test_db_connection()
        db_elapsed = time.perf_counter() - db_start

        db_status = "online" if db_online else "offline"
        database_latency_ms = round(db_elapsed * 1000, 1) if db_online else None

        cache_latency_ms: float | None = None
        try:
            cache_start = time.perf_counter()
            cache_ping = await settings.redis.get_client().ping()
            cache_elapsed = time.perf_counter() - cache_start
            cache_latency_ms = round(cache_elapsed * 1000, 1) if cache_ping else None
        except RedisError:  # pragma: no cover
            cache_ping = False

        cache_status = "online" if cache_ping else "offline"

        uptime = format_uptime(datetime.now(tz=UTC) - APP_START_TIME)

        healthy = cache_ping and db_online
        log_extra = {
            "database_status": db_status,
            "cache_status": cache_status,
            "controller": "system",
        }
        if healthy:
            logger.debug("System Health Check", extra=log_extra)
        else:
            logger.warning("System Health Check", extra=log_extra)  # pragma: no cover

        return Response(
            content=dto.SystemHealth(
                database_status=db_status,  # type: ignore [arg-type]
                cache_status=cache_status,  # type: ignore [arg-type]
                database_latency_ms=database_latency_ms,
                cache_latency_ms=cache_latency_ms,
                uptime=uptime,
            ),
            status_code=200 if healthy else 500,
            media_type=MediaType.JSON,
        )
