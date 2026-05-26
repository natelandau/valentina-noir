"""Log configuration."""

import sys
from pathlib import Path
from typing import Any

from litestar.logging.config import LoggingConfig

from vapi.config import settings
from vapi.lib.exceptions import (
    ConflictError,
    NoFieldsToUpdateError,
    NotAuthorizedError,
    NotEnoughXPError,
    NotFoundError,
    PermissionDeniedError,
    TooManyRequestsError,
    ValidationError,
)
from vapi.lib.log_formatters import ColorFormatter, LitestarJsonFormatter, StandardFormatter
from vapi.middleware.request_logging import CombinedLoggingMiddlewareConfig


def get_logging_config() -> LoggingConfig:
    """Get the logging configuration."""

    def _is_tty() -> bool:
        return bool(sys.stderr.isatty() or sys.stdout.isatty())

    handler_call_list = ["console"]
    handlers: dict[str, dict[str, Any]] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json"
            if settings.log.json_console
            else "color"
            if _is_tty()
            else "standard",
        },
    }
    if settings.log.file_path:
        handler_call_list.append("app_file")
        base_log_path = Path(settings.log.file_path).expanduser().resolve()
        base_log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers["app_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": base_log_path,
            # Append so log history survives restarts; size-based rotation still caps growth
            "mode": "a",
            "maxBytes": 32 * 1024 * 1024,  # 32 MiB
            "backupCount": 2,
            "encoding": "utf-8",
            "formatter": "json",
        }

    return LoggingConfig(
        log_exceptions=settings.log.log_exceptions,
        disable_stack_trace={
            400,
            401,
            403,
            404,
            409,
            NoFieldsToUpdateError,
            NotAuthorizedError,
            PermissionDeniedError,
            ValidationError,
            ValueError,
            NotFoundError,
            ConflictError,
            TooManyRequestsError,
            NotEnoughXPError,
        },
        formatters={
            "standard": {
                "()": StandardFormatter,
                "format": "[{asctime}] [{levelname}] {name}: {message}",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "style": "{",
            },
            "color": {
                "()": ColorFormatter,
            },
            "json": {
                "()": LitestarJsonFormatter,
                "format": "{levelname}{name}{message}{asctime}{exc_info}",
                "style": "{",
                "datefmt": "%Y-%m-%dT%H:%M:%SZ",
                "rename_fields": {
                    "levelname": "level",
                    "asctime": "timestamp",
                    "exc_info": "exception",
                },
            },
        },
        handlers=handlers,
        loggers={
            "litestar": {
                "propagate": False,
                "level": settings.log.level.value,
                "handlers": handler_call_list,
            },
            "_granian": {
                "propagate": False,
                "level": settings.log.asgi_server_level.value,
                "handlers": handler_call_list,
            },
            "granian.server": {
                "propagate": False,
                "level": settings.log.asgi_server_level.value,
                "handlers": handler_call_list,
            },
            "granian.access": {
                "propagate": False,
                "level": settings.log.asgi_server_level.value,
                "handlers": handler_call_list,
            },
            "saq": {
                "propagate": False,
                "level": settings.log.saq_level.value,
                "handlers": handler_call_list,
            },
            "vapi": {
                "propagate": False,
                "level": settings.log.level.value,
                "handlers": handler_call_list,
            },
        },
        root={
            "level": settings.log.root_level.value,
            "handlers": handler_call_list,
        },
    )


middleware_logging_config = CombinedLoggingMiddlewareConfig(
    log_fields=settings.log.log_fields,
    response_headers_to_obfuscate=settings.log.obfuscate_headers,
    response_cookies_to_obfuscate=settings.log.obfuscate_cookies,
    request_cookies_to_obfuscate=settings.log.obfuscate_cookies,
    request_headers_to_obfuscate=settings.log.obfuscate_headers,
)
