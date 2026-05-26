"""Tests for the combined request/response logging middleware and its config."""

import logging
from collections.abc import AsyncGenerator, Callable

from litestar import Litestar, get, post
from litestar.logging import LoggingConfig
from litestar.response import Stream
from litestar.testing import TestClient

from vapi.constants import LOG_FIELD_ROUTING, LOG_FIELDS_CATALOG
from vapi.middleware.request_logging import CombinedLoggingMiddlewareConfig

# Public log-field names that carry a request_/response_ prefix because their
# litestar extractor field (body, headers) exists on both the request and response.
_PREFIXED_COLLISION_FIELDS = {
    "request_body",
    "request_headers",
    "response_body",
    "response_headers",
}


def test_catalog_is_derived_from_routing() -> None:
    """Ensure the catalog stays in lockstep with the routing table."""
    # Given the routing table is the single source of truth
    # When the catalog is derived from it
    # Then the catalog matches the routing keys and includes known fields
    assert frozenset(LOG_FIELD_ROUTING) == LOG_FIELDS_CATALOG
    assert "path" in LOG_FIELDS_CATALOG
    assert "duration_ms" in LOG_FIELDS_CATALOG


def test_routing_targets_are_well_formed() -> None:
    """Verify every routing entry has a valid target and the key fields route correctly."""
    # Given the set of valid routing targets
    valid_targets = {"request", "response", "synthetic"}

    # When inspecting each (target, extractor_field) pair
    # Then every target is known and the key fields route as expected
    assert all(target in valid_targets for target, _ in LOG_FIELD_ROUTING.values())
    assert LOG_FIELD_ROUTING["duration_ms"] == ("synthetic", "duration_ms")
    assert LOG_FIELD_ROUTING["request_body"] == ("request", "body")
    assert LOG_FIELD_ROUTING["response_body"] == ("response", "body")
    assert LOG_FIELD_ROUTING["status_code"] == ("response", "status_code")


def test_only_collision_fields_are_prefixed() -> None:
    """Confirm only the body/headers collision fields carry a request_/response_ prefix."""
    # Given the routing table
    # When comparing each public name to its litestar extractor field
    # Then a name differs from its extractor field only for the prefixed collision fields
    renamed = {
        name for name, (_, extractor_field) in LOG_FIELD_ROUTING.items() if name != extractor_field
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
