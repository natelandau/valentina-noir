"""Log configuration."""

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from litestar.logging.config import LoggingConfig
from tortoise.exceptions import DoesNotExist as TortoiseDoesNotExist
from tortoise.exceptions import IntegrityError as TortoiseIntegrityError
from tortoise.exceptions import ValidationError as TortoiseValidationError

from vapi.config import settings
from vapi.constants import ERROR_TYPE_STATE_KEY, REQUEST_ID_STATE_KEY
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

if TYPE_CHECKING:
    from litestar.types import Logger, Scope


def log_uncaught_exception(logger: "Logger", scope: "Scope", _tb: list[str]) -> None:
    """Log an uncaught exception at ERROR with request correlation, and record its type.

    Litestar invokes this only for exceptions not suppressed by ``disable_stack_trace`` (so
    handled 4xx are excluded). It runs before the response is produced, so stashing the
    exception type on scope state lets the combined request entry surface ``error_type`` for
    unhandled errors, and the ``request_id`` ties this traceback line to that entry.
    """
    exc_type = sys.exc_info()[0]
    state = scope.get("state")
    if isinstance(state, dict) and exc_type is not None:
        state.setdefault(ERROR_TYPE_STATE_KEY, exc_type.__name__)

    request_id = state.get(REQUEST_ID_STATE_KEY) if isinstance(state, dict) else None
    developer_id = getattr(scope.get("user"), "id", None)
    logger.exception(
        "Uncaught exception",
        extra={
            "path": scope.get("path"),
            "request_id": request_id,
            "developer_id": str(developer_id) if developer_id is not None else None,
        },
    )


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
        exception_logging_handler=log_uncaught_exception,
        # These are expected client errors handled into clean responses and surfaced in the
        # combined request entry; suppress their tracebacks. Genuine bugs (ValueError,
        # KeyError, etc.) are intentionally absent so they log with a full traceback. The
        # Tortoise classes are the raw exceptions our handlers convert to 4xx (DoesNotExist
        # -> 404, IntegrityError -> 409, ValidationError -> 400); OperationalError is omitted
        # because it converts to a 500 and warrants a traceback.
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
            NotFoundError,
            ConflictError,
            TooManyRequestsError,
            NotEnoughXPError,
            TortoiseDoesNotExist,
            TortoiseIntegrityError,
            TortoiseValidationError,
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
