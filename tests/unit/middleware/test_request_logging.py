"""Tests for the combined request/response logging middleware and its config."""

import logging
from collections.abc import AsyncGenerator, Callable
from types import SimpleNamespace

import pytest
from litestar import Litestar, Response, get, post
from litestar.logging import LoggingConfig
from litestar.response import Stream
from litestar.testing import TestClient

from vapi.constants import LOG_FIELD_TARGETS, LOG_FIELDS_CATALOG
from vapi.lib.exceptions import (
    ConflictError,
    HTTPError,
    ValidationError,
    http_error_to_http_response,
)
from vapi.lib.log_config import log_uncaught_exception
from vapi.lib.log_formatters import StructuredMessageParser
from vapi.middleware.request_id import request_id_middleware
from vapi.middleware.request_logging import (
    CombinedLoggingMiddleware,
    CombinedLoggingMiddlewareConfig,
    _extract_scope_log_fields,
    _level_for_status,
    _render_value,
)

# Public log-field names that carry a request_/response_ prefix because their
# litestar extractor field (body, headers) exists on both the request and response.
_PREFIXED_COLLISION_FIELDS = {
    "request_body",
    "request_headers",
    "response_body",
    "response_headers",
}


def test_catalog_is_derived_from_targets() -> None:
    """Ensure the catalog stays in lockstep with the targets table."""
    # Given the targets table is the single source of truth
    # When the catalog is derived from it
    # Then the catalog matches the field names and includes known fields
    assert frozenset(LOG_FIELD_TARGETS) == LOG_FIELDS_CATALOG
    assert "path" in LOG_FIELDS_CATALOG
    assert "duration_ms" in LOG_FIELDS_CATALOG


def test_targets_are_well_formed() -> None:
    """Verify every field maps to a valid target and the key fields route correctly."""
    # Given the set of valid targets
    valid_targets = {"request", "response", "synthetic", "scope"}

    # When inspecting each field's target
    # Then every target is known and the key fields route as expected
    assert all(target in valid_targets for target in LOG_FIELD_TARGETS.values())
    assert LOG_FIELD_TARGETS["duration_ms"] == "synthetic"
    assert LOG_FIELD_TARGETS["request_body"] == "request"
    assert LOG_FIELD_TARGETS["response_body"] == "response"
    assert LOG_FIELD_TARGETS["status_code"] == "response"
    assert LOG_FIELD_TARGETS["request_id"] == "scope"


def test_only_collision_fields_are_prefixed() -> None:
    """Confirm only the body/headers collision fields carry a request_/response_ prefix."""
    # Given the targets table
    # When finding request/response fields whose name differs from its extractor field
    # Then only the body/headers collision fields carry a request_/response_ prefix
    renamed = {
        name
        for name, target in LOG_FIELD_TARGETS.items()
        if target in {"request", "response"}
        and name != name.removeprefix("request_").removeprefix("response_")
    }
    assert renamed == _PREFIXED_COLLISION_FIELDS


def test_config_translates_log_fields_to_extractor_fields() -> None:
    """Split log_fields into per-side extractor field tuples and flag duration."""
    # Given a combined config with request, response, collision, and synthetic fields
    config = CombinedLoggingMiddlewareConfig(
        log_fields=["path", "request_body", "response_body", "status_code", "duration_ms"]
    )
    # When __post_init__ runs the translation
    # Then fields are split per side, prefixes stripped, and duration flagged
    assert config.request_log_fields == ("path", "body")
    assert config.response_log_fields == ("body", "status_code")
    assert config.include_duration is True


def test_config_without_duration_field() -> None:
    """Leave include_duration false when duration_ms is not requested."""
    # Given a config with no duration_ms field
    config = CombinedLoggingMiddlewareConfig(log_fields=["path", "status_code"])
    # When translated
    # Then duration is not included
    assert config.include_duration is False


def test_config_translates_scope_fields() -> None:
    """Route scope-derived field names into scope_log_fields, leaving extractors empty."""
    # Given a config with only scope-derived fields
    config = CombinedLoggingMiddlewareConfig(
        log_fields=["request_id", "developer_id", "operation_id", "idempotency_key"]
    )
    # When __post_init__ runs the translation
    # Then they land in scope_log_fields and no request/response extractor fields are set
    assert config.scope_log_fields == [
        "request_id",
        "developer_id",
        "operation_id",
        "idempotency_key",
    ]
    assert config.request_log_fields == ()
    assert config.response_log_fields == ()


def test_extract_scope_fields_reads_from_scope() -> None:
    """Verify scope-derived fields are read from state, user, and route handler."""
    # Given a scope carrying request_id, idempotency key, acting user, developer, handler, and error
    scope = {
        "state": {
            "request_id": "req_abc",
            "idempotency_key": "idem_xyz",
            "acting_user": SimpleNamespace(id="user-9"),
            "error_detail": "already exists",
            "error_type": "ConflictError",
            "invalid_parameters": [{"field": "name", "message": "too long"}],
        },
        "user": SimpleNamespace(id="dev-123"),
        "route_handler": SimpleNamespace(operation_id="getThing"),
    }
    # When the configured scope fields are extracted
    values = _extract_scope_log_fields(
        scope,
        [
            "request_id",
            "developer_id",
            "operation_id",
            "idempotency_key",
            "acting_user_id",
            "error_detail",
            "error_type",
            "invalid_parameters",
        ],
    )
    # Then each field resolves to its scope-derived value
    assert values == {
        "request_id": "req_abc",
        "developer_id": "dev-123",
        "operation_id": "getThing",
        "idempotency_key": "idem_xyz",
        "acting_user_id": "user-9",
        "error_detail": "already exists",
        "error_type": "ConflictError",
        "invalid_parameters": [{"field": "name", "message": "too long"}],
    }


def test_extract_scope_fields_omits_absent_values() -> None:
    """Verify absent scope values are omitted rather than logged as null."""
    # Given a scope with no request_id, user, route handler, idempotency key, or acting user
    scope = {"state": {}}
    # When the configured scope fields are extracted
    values = _extract_scope_log_fields(
        scope,
        ["request_id", "developer_id", "operation_id", "idempotency_key", "acting_user_id"],
    )
    # Then no keys are produced
    assert values == {}


def test_extract_scope_fields_omits_callable_operation_id() -> None:
    """Verify a callable operation_id is skipped since only string ids are loggable."""
    # Given a route handler whose operation_id is a callable rather than a string
    scope = {"state": {}, "route_handler": SimpleNamespace(operation_id=lambda: "x")}
    # When the operation_id scope field is extracted
    values = _extract_scope_log_fields(scope, ["operation_id"])
    # Then the callable operation_id is omitted
    assert values == {}


class _CaptureHandler(logging.Handler):
    """Collect emitted log records for assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _build_app(config: CombinedLoggingMiddlewareConfig) -> Litestar:
    @post("/echo")
    async def echo(data: dict) -> dict:
        """Echo the posted JSON body back to the caller."""
        return data

    return Litestar(
        route_handlers=[echo],
        middleware=[config.middleware],
        logging_config=LoggingConfig(
            loggers={"litestar": {"level": "INFO", "handlers": [], "propagate": True}}
        ),
    )


def _capture(app: Litestar, make_request: Callable[[TestClient], object]) -> list[str]:
    handler = _CaptureHandler()
    with TestClient(app=app) as client:
        logger = logging.getLogger("litestar")
        original_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            make_request(client)
        finally:
            # Restore the prior level so capturing here does not leak global logger state to later tests
            logger.removeHandler(handler)
            logger.setLevel(original_level)
    return [record.getMessage() for record in handler.records]


def _capture_request(config: CombinedLoggingMiddlewareConfig, **request_kwargs) -> list[str]:
    return _capture(_build_app(config), lambda client: client.post("/echo", **request_kwargs))


def _capture_records(
    app: Litestar,
    make_request: Callable[[TestClient], object],
    *,
    raise_server_exceptions: bool = True,
) -> list[logging.LogRecord]:
    handler = _CaptureHandler()
    with TestClient(app=app, raise_server_exceptions=raise_server_exceptions) as client:
        logger = logging.getLogger("litestar")
        original_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            make_request(client)
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)
    return handler.records


def _build_status_app(config: CombinedLoggingMiddlewareConfig) -> Litestar:
    @get("/status/{code:int}")
    async def echo_status(code: int) -> Response:
        """Return an empty response carrying the requested status code."""
        return Response(content=b"", status_code=code)

    return Litestar(
        route_handlers=[echo_status],
        middleware=[config.middleware],
        logging_config=LoggingConfig(
            loggers={"litestar": {"level": "INFO", "handlers": [], "propagate": True}}
        ),
    )


@pytest.mark.parametrize(
    ("status_code", "expected_level"),
    [
        (200, logging.INFO),
        (201, logging.INFO),
        (302, logging.INFO),
        (400, logging.INFO),
        (404, logging.INFO),
        (409, logging.INFO),
        (422, logging.INFO),
        (401, logging.WARNING),
        (403, logging.WARNING),
        (429, logging.WARNING),
        (500, logging.ERROR),
        (503, logging.ERROR),
    ],
)
def test_level_for_status_tiers(status_code: int, expected_level: int) -> None:
    """Verify status codes map to tiered levels: auth/abuse WARNING, 5xx ERROR, else INFO."""
    # Given a response status code
    # When the combined entry's log level is derived from it
    level = _level_for_status(status_code)
    # Then it matches the tiered mapping
    assert level == expected_level


@pytest.mark.parametrize(
    ("status_code", "expected_level"),
    [
        (200, logging.INFO),
        (404, logging.INFO),
        (401, logging.WARNING),
        (429, logging.WARNING),
        (500, logging.ERROR),
    ],
)
def test_combined_entry_level_follows_status(status_code: int, expected_level: int) -> None:
    """Verify the combined entry is emitted at the level matching the response status class."""
    # Given an app whose handler returns the requested status code
    config = CombinedLoggingMiddlewareConfig(log_fields=["path", "status_code"])
    app = _build_status_app(config)

    # When a request returns that status
    records = _capture_records(app, lambda client: client.get(f"/status/{status_code}"))

    # Then exactly one combined entry is logged at the tiered level
    entries = [r for r in records if "path=/status" in r.getMessage()]
    assert len(entries) == 1
    assert entries[0].levelno == expected_level


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/api/v1/x", "/api/v1/x"),
        ("req_abc", "req_abc"),
        (409, "409"),
        ("already exists", '"already exists"'),
        ("a,b", '"a,b"'),
    ],
)
def test_render_value_quotes_only_when_needed(value: object, expected: str) -> None:
    """Verify string values with spaces/commas are quoted so the key=value parser keeps them whole."""
    # Given a field value
    # When it is rendered for the key=value message
    rendered = _render_value(value)
    # Then it is quoted only when it contains a space or comma
    assert rendered == expected


def test_render_value_round_trips_embedded_quotes() -> None:
    """Verify a value with spaces and embedded double-quotes survives the key=value round trip."""
    # Given free-text with spaces and embedded double-quotes (e.g. a Postgres constraint name)
    value = 'constraint "users_name_key" violated'
    # When rendered into a key=value pair and parsed back by the JSON formatter's parser
    message = f"error_detail={_render_value(value)}"
    parsed = StructuredMessageParser().parse(message)
    # Then the full value is preserved, not truncated at the first embedded quote
    assert parsed["error_detail"] == value


def test_log_message_tolerates_unmapped_level() -> None:
    """Verify log_message falls back to info for a level outside the known map instead of raising."""

    # Given a middleware instance with a captured stdlib logger
    async def _app(scope: object, receive: object, send: object) -> None:
        """No-op ASGI app for constructing the middleware."""

    config = CombinedLoggingMiddlewareConfig(log_fields=["path"])
    middleware = CombinedLoggingMiddleware(app=_app, config=config)
    handler = _CaptureHandler()
    logger = logging.getLogger("test_log_message_unmapped_level")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    middleware.logger = logger
    middleware.is_struct_logger = False

    # When log_message is called with a level absent from _LEVEL_METHODS
    try:
        middleware.log_message({"message": "HTTP Request", "path": "/x"}, level=logging.DEBUG)
    finally:
        logger.removeHandler(handler)

    # Then it emits one record without raising (falling back to info)
    assert len(handler.records) == 1


def test_handled_error_folds_into_single_entry() -> None:
    """Verify a handled HTTPError yields one combined entry carrying the reason, no separate ERROR line."""
    # Given an app that converts HTTPError via the app handler and logs the combined entry
    config = CombinedLoggingMiddlewareConfig(
        log_fields=["path", "status_code", "error_type", "error_detail"]
    )

    @get("/conflict")
    async def conflict() -> None:
        """Raise a handled conflict error."""
        raise ConflictError(detail="already exists")

    app = Litestar(
        route_handlers=[conflict],
        middleware=[config.middleware],
        exception_handlers={HTTPError: http_error_to_http_response},
        logging_config=LoggingConfig(
            loggers={"litestar": {"level": "INFO", "handlers": [], "propagate": True}}
        ),
    )

    # When the endpoint raises the handled error
    records = _capture_records(app, lambda client: client.get("/conflict"))

    # Then exactly one combined entry carries the reason, at INFO (409 is routine 4xx)
    entries = [r for r in records if "path=/conflict" in r.getMessage()]
    assert len(entries) == 1
    assert entries[0].levelno == logging.INFO
    assert "error_type=ConflictError" in entries[0].getMessage()
    assert 'error_detail="already exists"' in entries[0].getMessage()
    # And no invalid_parameters noise for an error that has none, and no standalone ERROR line
    assert "invalid_parameters=" not in entries[0].getMessage()
    assert [r for r in records if r.levelno == logging.ERROR] == []


def test_validation_error_folds_invalid_parameters_into_entry() -> None:
    """Verify a ValidationError's invalid_parameters are folded into the single combined entry."""
    # Given an app whose handler raises a validation error with field-level detail
    config = CombinedLoggingMiddlewareConfig(
        log_fields=["path", "status_code", "error_type", "invalid_parameters"]
    )

    @get("/validate")
    async def validate() -> None:
        """Raise a validation error carrying invalid parameters."""
        raise ValidationError(
            detail="bad", invalid_parameters=[{"field": "name", "message": "too long"}]
        )

    app = Litestar(
        route_handlers=[validate],
        middleware=[config.middleware],
        exception_handlers={HTTPError: http_error_to_http_response},
        logging_config=LoggingConfig(
            loggers={"litestar": {"level": "INFO", "handlers": [], "propagate": True}}
        ),
    )

    # When the endpoint raises the validation error
    records = _capture_records(app, lambda client: client.get("/validate"))

    # Then the single entry carries the field-level detail
    entries = [r for r in records if "path=/validate" in r.getMessage()]
    assert len(entries) == 1
    assert "error_type=ValidationError" in entries[0].getMessage()
    assert "invalid_parameters=[" in entries[0].getMessage()
    assert "too long" in entries[0].getMessage()


def test_unhandled_exception_logs_traceback_and_marks_combined_entry() -> None:
    """Verify an unhandled exception logs a correlated traceback line and an ERROR combined entry."""
    # Given an app whose handler raises an unhandled exception, with exception logging on
    config = CombinedLoggingMiddlewareConfig(log_fields=["path", "status_code", "error_type"])

    @get("/boom")
    async def boom() -> None:
        """Raise an unhandled exception."""
        msg = "boom"
        raise KeyError(msg)

    app = Litestar(
        route_handlers=[boom],
        middleware=[request_id_middleware, config.middleware],
        logging_config=LoggingConfig(
            log_exceptions="always",
            exception_logging_handler=log_uncaught_exception,
            loggers={"litestar": {"level": "INFO", "handlers": [], "propagate": True}},
        ),
    )

    # When the endpoint raises (server returns a 500 rather than re-raising into the test)
    records = _capture_records(
        app, lambda client: client.get("/boom"), raise_server_exceptions=False
    )

    # Then a traceback line is logged at ERROR with the exception and the request id
    traceback_lines = [r for r in records if r.getMessage() == "Uncaught exception"]
    assert len(traceback_lines) == 1
    assert traceback_lines[0].levelno == logging.ERROR
    assert traceback_lines[0].exc_info is not None
    assert getattr(traceback_lines[0], "request_id", "").startswith("req_")

    # And the single combined entry is ERROR (500) and carries the stashed error_type
    entries = [r for r in records if "path=/boom" in r.getMessage()]
    assert len(entries) == 1
    assert entries[0].levelno == logging.ERROR
    assert "error_type=KeyError" in entries[0].getMessage()


def test_combined_entry_level_independent_of_configured_fields() -> None:
    """Verify the level follows the response status even when status_code is not a logged field."""
    # Given a config that does not include status_code as a logged field
    config = CombinedLoggingMiddlewareConfig(log_fields=["path"])
    app = _build_status_app(config)

    # When the handler returns a 500
    records = _capture_records(app, lambda client: client.get("/status/500"))

    # Then the combined entry is still emitted at ERROR
    entries = [r for r in records if "path=/status" in r.getMessage()]
    assert len(entries) == 1
    assert entries[0].levelno == logging.ERROR


def test_single_combined_entry_per_request() -> None:
    """Emit exactly one merged entry carrying request, response, and duration fields."""
    # Given an app using the combined middleware
    config = CombinedLoggingMiddlewareConfig(
        log_fields=["path", "method", "status_code", "duration_ms"]
    )
    # When one request is made
    messages = _capture_request(config, json={"x": 1})
    # Then exactly one entry carries the merged request+response fields and duration
    entries = [m for m in messages if "path=" in m]
    assert len(entries) == 1
    entry = entries[0]
    assert "path=/echo" in entry
    assert "method=POST" in entry
    assert "status_code=201" in entry
    assert "duration_ms=" in entry


def test_request_id_appears_in_combined_entry() -> None:
    """Verify the request_id set by RequestIdMiddleware is rendered into the combined entry."""
    # Given an app with the request-id middleware ahead of the combined logging middleware
    config = CombinedLoggingMiddlewareConfig(log_fields=["path", "request_id", "status_code"])

    @post("/echo")
    async def echo(data: dict) -> dict:
        """Echo the posted JSON body back to the caller."""
        return data

    app = Litestar(
        route_handlers=[echo],
        middleware=[request_id_middleware, config.middleware],
        logging_config=LoggingConfig(
            loggers={"litestar": {"level": "INFO", "handlers": [], "propagate": True}}
        ),
    )
    # When a request is made
    messages = _capture(app, lambda client: client.post("/echo", json={"x": 1}))
    # Then exactly one combined entry carries the generated request_id from scope state
    entries = [m for m in messages if "path=/echo" in m]
    assert len(entries) == 1
    assert "request_id=req_" in entries[0]


def test_collision_fields_are_prefixed_by_side() -> None:
    """Render request_body and response_body under their prefixed names in one entry."""
    # Given request_body and response_body both requested
    config = CombinedLoggingMiddlewareConfig(
        log_fields=["request_body", "response_body", "status_code"]
    )
    # When a request with a body is made
    messages = _capture_request(config, json={"hello": "world"})
    # Then both sides appear under their prefixed names in one entry
    entries = [m for m in messages if "status_code=" in m]
    assert len(entries) == 1
    assert "request_body=" in entries[0]
    assert "response_body=" in entries[0]


def test_sensitive_request_header_is_obfuscated() -> None:
    """Obfuscate a secret Authorization header rather than logging it in cleartext."""
    # Given request_headers requested and a secret Authorization header sent
    config = CombinedLoggingMiddlewareConfig(log_fields=["request_headers", "status_code"])
    # When the request includes an Authorization header
    messages = _capture_request(
        config, json={"x": 1}, headers={"Authorization": "Bearer supersecret"}
    )
    # Then the secret is obfuscated, not logged in cleartext
    entries = [m for m in messages if "status_code=" in m]
    assert len(entries) == 1
    assert "supersecret" not in entries[0]
    assert "*****" in entries[0]


def test_empty_log_fields_emits_no_entry() -> None:
    """Stay silent when no fields are configured (logging effectively off)."""
    # Given a config with no log fields
    config = CombinedLoggingMiddlewareConfig(log_fields=[])
    # When a request is made
    messages = _capture_request(config, json={"x": 1})
    # Then the middleware emits no combined entry
    assert not any("HTTP Request" in message for message in messages)


def test_streaming_response_logs_single_entry() -> None:
    """Verify a multi-chunk streaming response produces exactly one combined entry."""
    # Given an app whose route streams several body chunks
    config = CombinedLoggingMiddlewareConfig(log_fields=["path", "status_code", "duration_ms"])

    async def _chunks() -> AsyncGenerator[bytes]:
        for part in (b"alpha", b"beta", b"gamma"):
            yield part

    @get("/stream")
    async def stream() -> Stream:
        """Return a streaming response of several chunks."""
        return Stream(_chunks())

    app = Litestar(
        route_handlers=[stream],
        middleware=[config.middleware],
        logging_config=LoggingConfig(
            loggers={"litestar": {"level": "INFO", "handlers": [], "propagate": True}}
        ),
    )

    # When the streamed response completes
    messages = _capture(app, lambda client: client.get("/stream"))

    # Then exactly one entry is emitted despite the multiple body chunks
    entries = [message for message in messages if "path=/stream" in message]
    assert len(entries) == 1
