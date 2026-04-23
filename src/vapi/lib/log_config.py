"""Log configuration."""

import ast
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, ClassVar

from litestar.logging.config import LoggingConfig
from litestar.middleware.logging import LoggingMiddlewareConfig
from pythonjsonlogger.core import RESERVED_ATTRS
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

_KV_VALUE_PATTERN = (
    r"(?:\{(?:[^{}]|\{[^{}]*\})*\})"
    r"|(?:\[(?:[^\[\]]|\[[^\[\]]*\])*\])"
    r'|(?:"[^"]*")'
    r"|(?:'[^']*')"
    r"|(?:[^,\s]+)"
)
_STRUCTURED_KV_RE = re.compile(rf"(\w+)=({_KV_VALUE_PATTERN})")
_STRUCTURED_KV_STRIP_RE = re.compile(rf"\s*\w+=(?:{_KV_VALUE_PATTERN})")


def _sanitize_binary_body(message: str) -> str:
    """Strip binary payload bodies and multipart boundaries from a log message, keeping metadata."""
    # Cheap substring guards avoid running catastrophic-backtracking-prone regex on every log line
    if "Content-Type:" in message:
        message = BINARY_CONTENT_PATTERN.sub(r"\1 [binary content omitted]", message)
    if "------" in message:
        message = MULTIPART_BOUNDARY_PATTERN.sub("", message)
    return message


class BaseFormatter(logging.Formatter):
    """Base formatter with shared functionality for binary sanitization and extra fields."""

    _RESERVED_KEYS: ClassVar[frozenset[str]] = frozenset(RESERVED_ATTRS)

    def _get_extra_fields(self, record: logging.LogRecord) -> dict[str, Any]:
        """Extract extra fields from log record that are not standard logging attributes."""
        return {k: v for k, v in record.__dict__.items() if k not in self._RESERVED_KEYS}

    def _sanitize_and_format(self, record: logging.LogRecord) -> str:
        """Sanitize the record message and format using the parent formatter.

        Subclasses should override this to use custom formatters while still
        benefiting from binary sanitization.

        Args:
            record: The log record to format.

        Returns:
            Formatted log string (without extra fields).
        """
        original_msg = record.msg
        record.msg = _sanitize_binary_body(str(record.msg))
        try:
            return super().format(record)
        finally:
            record.msg = original_msg

    def _append_extras(self, output: str, record: logging.LogRecord) -> str:
        """Append extra fields to the formatted output.

        Args:
            output: The already-formatted log string.
            record: The log record containing potential extra fields.

        Returns:
            Log string with extra fields appended.
        """
        extra = self._get_extra_fields(record)
        if extra:
            output += " " + str(extra)
        return output


class StandardFormatter(BaseFormatter):
    """Standard formatter with binary content sanitization."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record, sanitizing binary content."""
        output = self._sanitize_and_format(record)
        return self._append_extras(output, record)


class ColorFormatter(BaseFormatter):
    """Color formatter with ANSI escape codes for terminal output."""

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

    def _sanitize_and_format(self, record: logging.LogRecord) -> str:
        """Sanitize and format record using level-specific colored formatter."""
        formatter = self._FORMATS.get(record.levelno, self._FORMATS[logging.DEBUG])

        original_msg = record.msg
        original_exc_text = record.exc_text
        if record.exc_info:
            text = formatter.formatException(record.exc_info)
            record.exc_text = f"\x1b[31m{text}\x1b[0m"
        record.msg = _sanitize_binary_body(str(record.msg))

        try:
            return formatter.format(record)
        finally:
            record.msg = original_msg
            record.exc_text = original_exc_text

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colors."""
        output = self._sanitize_and_format(record)
        return self._append_extras(output, record)


class LitestarJsonFormatter(JsonFormatter):
    """JSON formatter that automatically extracts key=value pairs from log messages."""

    def add_fields(
        self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]
    ) -> None:
        """Add fields to the log record, parsing structured key=value pairs."""
        super().add_fields(log_record, record, message_dict)

        message = _sanitize_binary_body(record.getMessage())
        extracted = self.parse_structured_message(message)

        if extracted:
            log_record.update(extracted)
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
        # Cheap guard: skip regex walk on every log line that can't possibly contain a kv pair
        if "=" not in message:
            return {}
        return {key: self.parse_value(value) for key, value in _STRUCTURED_KV_RE.findall(message)}

    def _handle_numbers(self, value: str) -> int | float | None:
        """Parse a numeric string into int or float, returning None if not numeric."""
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return None

    def _handle_arrays(self, value: str) -> list | dict | None:
        """Parse a JSON object/array, falling back to Python literal syntax."""
        if not (
            (value.startswith("{") and value.endswith("}"))
            or (value.startswith("[") and value.endswith("]"))
        ):
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # ast.literal_eval handles Python-repr output (single quotes, None/True/False) safely
            try:
                parsed = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                return None
            return parsed if isinstance(parsed, list | dict) else None

    def _handle_quoted_strings(self, value: str) -> str | None:
        """Strip matching outer quotes from a quoted string, or return None if not quoted."""
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

        if value in ("None", "null", "NULL"):
            return None
        if value in ("True", "true", "TRUE"):
            return True
        if value in ("False", "false", "FALSE"):
            return False

        number = self._handle_numbers(value)
        if number is not None:
            return number

        array = self._handle_arrays(value)
        if array is not None:
            return array

        quoted_string = self._handle_quoted_strings(value)
        if quoted_string is not None:
            return quoted_string

        return value

    def clean_message(self, message: str) -> str:
        """Remove extracted key=value pairs from message, leaving non-extracted text intact."""
        cleaned = _STRUCTURED_KV_STRIP_RE.sub("", message)
        cleaned = re.sub(r",\s*,", ",", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,").rstrip(":")
        return cleaned or message


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
