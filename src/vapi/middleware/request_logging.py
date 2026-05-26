"""Combined request/response logging middleware.

Emit a single structured log entry per HTTP request, merging request fields,
response fields, and request duration into one line. Subclasses Litestar's
``LoggingMiddleware`` to reuse its data extractors, header/cookie obfuscation,
and message formatting while collapsing the framework's two-entry-per-request
behavior into one.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from litestar.constants import HTTP_RESPONSE_BODY, HTTP_RESPONSE_START
from litestar.middleware.logging import (
    LoggingMiddleware,
    LoggingMiddlewareConfig,
    structlog_installed,
)
from litestar.utils.scope.state import ScopeState

from vapi.constants import LOG_FIELD_ROUTING

if TYPE_CHECKING:
    from collections.abc import Collection

    from litestar.types import Message, Receive, Scope, Send

__all__ = ("CombinedLoggingMiddleware", "CombinedLoggingMiddlewareConfig")

# Litestar extractor field name -> public log_fields name, per side. Derived from
# the routing table so collision fields (body, headers) get their request_/response_
# prefix back on output, while bare fields keep their name.
_REQUEST_OUTPUT_NAMES = {
    extractor_field: name
    for name, (target, extractor_field) in LOG_FIELD_ROUTING.items()
    if target == "request"
}
_RESPONSE_OUTPUT_NAMES = {
    extractor_field: name
    for name, (target, extractor_field) in LOG_FIELD_ROUTING.items()
    if target == "response"
}


class CombinedLoggingMiddleware(LoggingMiddleware):
    """Emit one merged log entry per request instead of separate request/response entries."""

    config: CombinedLoggingMiddlewareConfig

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Capture request data, time the request, and log one combined entry on response.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive function.
            send: The ASGI send function.
        """
        if not hasattr(self, "logger"):
            self.logger = scope["litestar_app"].get_logger(self.config.logger_name)
            self.is_struct_logger = structlog_installed and repr(self.logger).startswith(
                "<BoundLoggerLazyProxy"
            )

        start = time.perf_counter()

        request_values: dict[str, Any] = {}
        if self.config.request_log_fields:
            # Reading the body here caches it on the scope so the handler can re-read it
            request = scope["litestar_app"].request_class(scope, receive)
            extracted = await self.extract_request_data(request=request)
            extracted.pop("message", None)
            request_values = {
                _REQUEST_OUTPUT_NAMES.get(key, key): value for key, value in extracted.items()
            }

        connection_state = ScopeState.from_scope(scope)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == HTTP_RESPONSE_START:
                connection_state.log_context[HTTP_RESPONSE_START] = message
            elif message["type"] == HTTP_RESPONSE_BODY:
                connection_state.log_context[HTTP_RESPONSE_BODY] = message
                # Log once, on the final body chunk, so a streamed (multi-chunk) response
                # produces a single combined entry rather than one entry per chunk
                if not message.get("more_body"):
                    self._log_combined(scope=scope, request_values=request_values, start=start)
                    connection_state.log_context.clear()
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _log_combined(self, scope: Scope, request_values: dict[str, Any], start: float) -> None:
        """Merge request data, response data, and duration into one ordered log entry.

        Args:
            scope: The ASGI connection scope.
            request_values: Request fields already extracted and renamed by side.
            start: ``perf_counter`` value captured when the request arrived.
        """
        merged: dict[str, Any] = dict(request_values)

        if self.config.response_log_fields:
            response_data = self.extract_response_data(scope=scope)
            response_data.pop("message", None)
            for key, value in response_data.items():
                merged[_RESPONSE_OUTPUT_NAMES.get(key, key)] = value

        if self.config.include_duration:
            merged["duration_ms"] = round((time.perf_counter() - start) * 1000)

        # Nothing configured to log: stay silent, matching the parent's "off = silent" semantics
        if not merged:
            return

        # Order output to match the configured log_fields list
        values: dict[str, Any] = {"message": self.config.request_log_message}
        for name in self.config.log_fields:
            if name in merged:
                values[name] = merged[name]

        self.log_message(values=values)


@dataclass
class CombinedLoggingMiddlewareConfig(LoggingMiddlewareConfig):
    """Logging middleware config driven by a single ordered ``log_fields`` list."""

    log_fields: Collection[str] = field(default=())
    include_duration: bool = field(default=False, init=False)
    middleware_class: type[LoggingMiddleware] = field(default=CombinedLoggingMiddleware)

    def __post_init__(self) -> None:
        """Translate ``log_fields`` into the request/response extractor field tuples."""
        request_fields: list[str] = []
        response_fields: list[str] = []
        for name in self.log_fields:
            target, extractor_field = LOG_FIELD_ROUTING[name]
            if target == "request":
                request_fields.append(extractor_field)
            elif target == "response":
                response_fields.append(extractor_field)
            else:  # synthetic (duration_ms)
                self.include_duration = True
        self.request_log_fields = request_fields  # type: ignore[assignment]
        self.response_log_fields = response_fields  # type: ignore[assignment]
        super().__post_init__()
