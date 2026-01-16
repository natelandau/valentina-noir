"""Log configuration."""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, ClassVar

from litestar.logging.config import LoggingConfig
from litestar.middleware.logging import LoggingMiddlewareConfig
from pythonjsonlogger.json import JsonFormatter

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

BINARY_CONTENT_PATTERN = re.compile(
    r"(Content-Type:\s*(?:image|audio|video|application/(?:octet-stream|pdf|zip|gzip|x-[^\s;]+))[^\s;]*)\s+.*",
    re.IGNORECASE | re.DOTALL,
)
MULTIPART_BOUNDARY_PATTERN = re.compile(r"------\w+\s*", re.MULTILINE)


def _sanitize_binary_body(message: str) -> str:
    """Remove binary content from message, keeping metadata."""
    sanitized = BINARY_CONTENT_PATTERN.sub(r"\1 [binary content omitted]", message)

    return MULTIPART_BOUNDARY_PATTERN.sub("", sanitized)


class StandardFormatter(logging.Formatter):
    """Standard formatter with binary content sanitization."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record, sanitizing binary content."""
        # Sanitize binary content from the message before formatting
        original_msg = record.msg
        record.msg = _sanitize_binary_body(str(record.msg))

        output = super().format(record)

        # Restore original message to avoid side effects
        record.msg = original_msg

        return output


class ColorFormatter(logging.Formatter):
    """Color formatter."""

    def_keys: ClassVar[list[str]] = [
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    ]

    _LEVEL_COLORS: ClassVar[list[tuple[int, str]]] = [
        (logging.DEBUG, "\x1b[40;1m"),
        (logging.INFO, "\x1b[34;1m"),
        (logging.WARNING, "\x1b[33;1m"),
        (logging.ERROR, "\x1b[31m"),
        (logging.CRITICAL, "\x1b[41m"),
    ]

    _FORMATS: ClassVar[dict[int, logging.Formatter]] = {
        level: logging.Formatter(
            f"\x1b[30;1m%(asctime)s\x1b[0m {color}%(levelname)-8s\x1b[0m \x1b[35m%(name)-9s\x1b[0m %(message)s"
            if settings.log.time_in_console
            else f"{color}%(levelname)-8s\x1b[0m \x1b[35m%(name)-9s\x1b[0m %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
        for level, color in _LEVEL_COLORS
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record."""
        formatter = self._FORMATS.get(record.levelno)
        if formatter is None:
            formatter = self._FORMATS[logging.DEBUG]

        if record.exc_info:
            text = formatter.formatException(record.exc_info)
            record.exc_text = f"\x1b[31m{text}\x1b[0m"

        # Sanitize binary content from the message before formatting
        original_msg = record.msg
        record.msg = _sanitize_binary_body(str(record.msg))

        output = formatter.format(record)

        # Restore original message to avoid side effects
        record.msg = original_msg

        # Add extra fields to the output
        extra = {k: v for k, v in record.__dict__.items() if k not in self.def_keys}
        if len(extra) > 0:
            output += " " + str(extra)

        record.exc_text = None
        return output


class LitestarJsonFormatter(JsonFormatter):
    """JSON formatter that automatically extracts key=value pairs from log messages."""

    def add_fields(
        self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]
    ) -> None:
        """Add fields to the log record, parsing structured key=value pairs."""
        # Call parent to get base fields
        super().add_fields(log_record, record, message_dict)

        # Parse any structured key=value pairs from the message
        message = record.getMessage()

        # Sanitize binary content before parsing
        message = _sanitize_binary_body(message)

        extracted = self.parse_structured_message(message)

        if extracted:
            # Add extracted fields directly to the root of the log record
            log_record.update(extracted)

            # Clean the message by removing extracted key=value pairs
            log_record["message"] = self.clean_message(message)
        else:
            log_record["message"] = message

    def parse_structured_message(self, message: str) -> dict[str, Any]:
        """Parse structured key=value format from message.

        Extracts patterns like:
        - key={...}  (dicts)
        - key=[...]  (lists)
        - key="..."  (quoted strings)
        - key=value  (unquoted values)
        """
        # Pattern to match key=value pairs where value can be:
        # - A dict: {...} (with nested braces support)
        # - A list: [...] (with nested brackets support)
        # - A quoted string: "..."
        # - An unquoted value: up to the next comma, space, or end
        pattern = r'(\w+)=((?:\{(?:[^{}]|\{[^{}]*\})*\})|(?:\[(?:[^\[\]]|\[[^\[\]]*\])*\])|(?:"[^"]*")|(?:\'[^\']*\')|(?:[^,\s]+))'

        matches = re.findall(pattern, message)

        extracted: dict[str, Any] = {}
        for key, value in matches:
            parsed_value = self.parse_value(value)
            extracted[key] = parsed_value

        return extracted

    def _handle_numbers(self, value: str) -> int | float | None:
        """Handle numbers."""
        if value.replace(".", "", 1).replace("-", "", 1).replace("+", "", 1).isdigit():
            try:
                if "." in value:
                    return float(value)
                return int(value)
            except ValueError:
                pass

        return None

    def _handle_arrays(self, value: str) -> list | None:
        """Handle arrays."""
        if (value.startswith("{") and value.endswith("}")) or (
            value.startswith("[") and value.endswith("]")
        ):
            try:
                # Try with double quotes first
                return json.loads(value)
            except json.JSONDecodeError:
                try:
                    json_value = value.replace("'", '"')
                    json_value = json_value.replace("None", "null")
                    json_value = json_value.replace("True", "true")
                    json_value = json_value.replace("False", "false")
                    return json.loads(json_value)
                except json.JSONDecodeError:
                    pass
        return None

    def _handle_quoted_strings(self, value: str) -> str | None:
        """Handle quoted strings."""
        if len(value) >= 2 and (  # noqa: PLR2004
            (value.startswith('"') and value.endswith('"'))
            or (value.startswith("'") and value.endswith("'"))
        ):
            return value[1:-1]
        return None

    def parse_value(self, value: str) -> dict | list | int | float | bool | None | str:  # noqa: PLR0911
        """Parse a value string into the appropriate Python type.

        Returns:
            Parsed value as dict, list, int, float, bool, None, or str
        """
        value = value.strip()

        # Handle None/null
        if value in ("None", "null", "NULL"):
            return None
        # Handle booleans
        if value in ("True", "true", "TRUE"):
            return True
        if value in ("False", "false", "FALSE"):
            return False

        # Handle numbers
        if number := self._handle_numbers(value):
            return number

        # Handle JSON objects/arrays
        if array := self._handle_arrays(value):
            return array

        # Handle quoted strings (remove quotes)
        if quoted_string := self._handle_quoted_strings(value):
            return quoted_string

        # Return as string
        return value

    def clean_message(self, message: str) -> str:
        """Remove extracted key=value pairs from message, leaving non-extracted text intact."""
        # Remove all key=value patterns
        pattern = r'\s*\w+=((?:\{(?:[^{}]|\{[^{}]*\})*\})|(?:\[(?:[^\[\]]|\[[^\[\]]*\])*\])|(?:"[^"]*")|(?:\'[^\']*\')|(?:[^,\s]+))'
        cleaned = re.sub(pattern, "", message)

        # Clean up extra commas and spaces
        cleaned = re.sub(r",\s*,", ",", cleaned)
        cleaned = re.sub(r",\s*$", "", cleaned)  # Remove trailing comma
        cleaned = re.sub(r"^\s*,", "", cleaned)  # Remove leading comma
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip(", ").rstrip(":")

        return cleaned if cleaned else message


def get_logging_config() -> LoggingConfig:
    """Get the logging configuration."""

    def _is_tty() -> bool:
        return bool(sys.stderr.isatty() or sys.stdout.isatty())

    handler_call_list = ["console"]
    handlers: dict[str, dict[str, Any]] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "color" if _is_tty() else "standard",
        },
    }
    if settings.log.file_path:
        handler_call_list.append("app_file")
        base_log_path = Path(settings.log.file_path).expanduser().resolve()
        base_log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers["app_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": base_log_path,
            "mode": "w",
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
            "pymongo": {
                "propagate": False,
                "level": "ERROR",
                "handlers": handler_call_list,
            },
        },
        root={
            "level": settings.log.root_level.value,
            "handlers": handler_call_list,
        },
    )


middleware_logging_config = LoggingMiddlewareConfig(
    request_log_fields=settings.log.request_log_fields,  # type: ignore [arg-type]
    response_log_fields=settings.log.response_log_fields,  # type: ignore [arg-type]
    response_headers_to_obfuscate=settings.log.obfuscate_headers,
    response_cookies_to_obfuscate=settings.log.obfuscate_cookies,
    request_cookies_to_obfuscate=settings.log.obfuscate_cookies,
    request_headers_to_obfuscate=settings.log.obfuscate_headers,
)
