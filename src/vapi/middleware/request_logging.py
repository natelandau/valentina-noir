"""Combined request/response logging middleware.

Emit a single structured log entry per HTTP request, merging request fields,
response fields, and request duration into one line. Subclasses Litestar's
``LoggingMiddleware`` to reuse its data extractors, header/cookie obfuscation,
and message formatting while collapsing the framework's two-entry-per-request
behavior into one.
"""

from __future__ import annotations

import logging
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

from vapi.constants import (
    ERROR_DETAIL_STATE_KEY,
    ERROR_TYPE_STATE_KEY,
    IDEMPOTENCY_KEY_STATE_KEY,
    INVALID_PARAMETERS_STATE_KEY,
    LOG_FIELD_TARGETS,
    REQUEST_ID_STATE_KEY,
)

if TYPE_CHECKING:
    from collections.abc import Collection

    from litestar.types import Message, Receive, Scope, Send

__all__ = ("CombinedLoggingMiddleware", "CombinedLoggingMiddlewareConfig")

# Status codes that warrant WARNING rather than INFO: auth failures and rate-limit
# rejections are worth a glance (broken clients, credential probing, abuse) without
# being server faults. Routine 4xx (validation, not-found, conflict) stay INFO.
_WARNING_STATUS_CODES = frozenset({401, 403, 429})

_LEVEL_METHODS = {logging.INFO: "info", logging.WARNING: "warning", logging.ERROR: "error"}


def _render_value(value: Any) -> str:
    """Render a field value for the ``key=value`` message, quoting free-text when needed.

    The JSON formatter re-parses ``key=value`` pairs out of the message, and its parser
    stops an unquoted value at the first space or comma. Quote string values containing
    either so multi-word fields like ``error_detail`` survive the round trip intact, and
    backslash-escape embedded quotes/backslashes so a value like a DB constraint name in
    double quotes is not truncated at the first inner quote.
    """
    if isinstance(value, str) and (" " in value or "," in value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return str(value)


def _level_for_status(status_code: int) -> int:
    """Map an HTTP status code to a log level for the combined request entry.

    5xx are server faults (ERROR), auth/abuse rejections are worth attention (WARNING),
    and everything else, including routine 4xx client mistakes, is normal traffic (INFO).
    """
    if status_code >= 500:  # noqa: PLR2004
        return logging.ERROR
    if status_code in _WARNING_STATUS_CODES:
        return logging.WARNING
    return logging.INFO


# Maps Litestar's extractor field back to the public name, restoring the request_/
# response_ prefix so request and response body/headers stay distinct on output.
_REQUEST_OUTPUT_NAMES = {
    name.removeprefix("request_"): name
    for name, target in LOG_FIELD_TARGETS.items()
    if target == "request"
}
_RESPONSE_OUTPUT_NAMES = {
    name.removeprefix("response_"): name
    for name, target in LOG_FIELD_TARGETS.items()
    if target == "response"
}


# Scope fields read by a plain state lookup; the attribute-derived ones
# (developer_id, operation_id, acting_user_id) are handled as branches below.
_STATE_KEY_FIELDS = {
    "request_id": REQUEST_ID_STATE_KEY,
    "idempotency_key": IDEMPOTENCY_KEY_STATE_KEY,
    "error_detail": ERROR_DETAIL_STATE_KEY,
    "error_type": ERROR_TYPE_STATE_KEY,
    "invalid_parameters": INVALID_PARAMETERS_STATE_KEY,
}


def _extract_scope_log_fields(scope: Scope, field_names: Collection[str]) -> dict[str, Any]:
    """Read scope-derived log fields (request_id, developer_id, etc.) from the ASGI scope.

    These fields live on the scope rather than in the request/response payload: they are
    set by upstream middleware (request_id, auth, idempotency) or by routing. Values absent
    on the scope (unauthenticated routes, requests without an idempotency key, handlers with
    no operation_id) are skipped so the field is simply omitted rather than logged as null.

    Args:
        scope: The ASGI connection scope.
        field_names: The configured scope-derived field names to read.

    Returns:
        A mapping of present field names to their scope-derived values.
    """
    state = scope.get("state") or {}
    values: dict[str, Any] = {}

    for name in field_names:
        if name in _STATE_KEY_FIELDS:
            value: Any = state.get(_STATE_KEY_FIELDS[name])
        elif name == "developer_id":
            value = getattr(scope.get("user"), "id", None)
        elif name == "acting_user_id":
            # Guards resolving the On-Behalf-Of header stash the User here; absent otherwise
            value = getattr(state.get("acting_user"), "id", None)
        elif name == "operation_id":
            # Litestar allows operation_id to be a callable; only string ids are loggable
            operation_id = getattr(scope.get("route_handler"), "operation_id", None)
            value = operation_id if isinstance(operation_id, str) else None
        else:
            value = None

        if value is not None:
            values[name] = value

    return values


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
        status_code = 200

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == HTTP_RESPONSE_START:
                connection_state.log_context[HTTP_RESPONSE_START] = message
                # Capture the status here rather than re-reading it later, so the entry's
                # severity does not depend on the parent leaving the start message in place
                status_code = message.get("status", 200)
            elif message["type"] == HTTP_RESPONSE_BODY:
                connection_state.log_context[HTTP_RESPONSE_BODY] = message
                # Log once, on the final body chunk, so a streamed (multi-chunk) response
                # produces a single combined entry rather than one entry per chunk
                if not message.get("more_body"):
                    self._log_combined(
                        scope=scope,
                        request_values=request_values,
                        start=start,
                        status_code=status_code,
                    )
                    connection_state.log_context.clear()
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _log_combined(
        self, scope: Scope, request_values: dict[str, Any], start: float, status_code: int
    ) -> None:
        """Merge request data, response data, and duration into one ordered log entry.

        Args:
            scope: The ASGI connection scope.
            request_values: Request fields already extracted and renamed by side.
            start: ``perf_counter`` value captured when the request arrived.
            status_code: The response status, used to pick the entry's log level.
        """
        merged: dict[str, Any] = dict(request_values)

        if self.config.response_log_fields:
            response_data = self.extract_response_data(scope=scope)
            response_data.pop("message", None)
            for key, value in response_data.items():
                merged[_RESPONSE_OUTPUT_NAMES.get(key, key)] = value

        # Read scope-derived fields here (not at request start) so route-resolution fields
        # like operation_id, populated by the router after this middleware runs, are present
        if self.config.scope_log_fields:
            merged.update(_extract_scope_log_fields(scope, self.config.scope_log_fields))

        if self.config.include_duration:
            merged["duration_ms"] = round((time.perf_counter() - start) * 1000)

        # Nothing configured to log: stay silent, matching the parent's "off = silent" semantics
        if not merged:
            return

        # Emit in the operator's configured field order, not the order fields were merged
        values: dict[str, Any] = {"message": self.config.request_log_message}
        for name in self.config.log_fields:
            if name in merged:
                values[name] = merged[name]

        self.log_message(values=values, level=_level_for_status(status_code))

    def log_message(self, values: dict[str, Any], level: int = logging.INFO) -> None:
        """Log the combined entry at ``level`` instead of the parent's hardcoded INFO.

        Args:
            values: The ordered field values to log, including the ``message`` key.
            level: The ``logging`` level to emit at, derived from the response status.
        """
        message = values.pop("message")
        # Dispatch by method name: the Logger protocol exposes info/warning/error but not log().
        # Fall back to info for any level outside the map rather than raising mid-response.
        log = getattr(self.logger, _LEVEL_METHODS.get(level, "info"))
        if self.is_struct_logger:
            log(message, **values)
        else:
            value_strings = [f"{key}={_render_value(value)}" for key, value in values.items()]
            rendered = f"{message}: {', '.join(value_strings)}"
            log(rendered)


@dataclass
class CombinedLoggingMiddlewareConfig(LoggingMiddlewareConfig):
    """Logging middleware config driven by a single ordered ``log_fields`` list."""

    log_fields: Collection[str] = field(default=())
    include_duration: bool = field(default=False, init=False)
    scope_log_fields: list[str] = field(default_factory=list, init=False)
    middleware_class: type[LoggingMiddleware] = field(default=CombinedLoggingMiddleware)

    def __post_init__(self) -> None:
        """Translate ``log_fields`` into per-target field collections."""
        request_fields: list[str] = []
        response_fields: list[str] = []
        for name in self.log_fields:
            target = LOG_FIELD_TARGETS[name]
            if target == "request":
                request_fields.append(name.removeprefix("request_"))
            elif target == "response":
                response_fields.append(name.removeprefix("response_"))
            elif target == "scope":
                self.scope_log_fields.append(name)
            else:  # synthetic (duration_ms)
                self.include_duration = True
        self.request_log_fields = request_fields  # type: ignore[assignment]
        self.response_log_fields = response_fields  # type: ignore[assignment]
        super().__post_init__()
