"""Tests for authentication utilities."""

import logging
from types import SimpleNamespace

from vapi.utils.authentication import generate_api_key, log_auth_failure


class _CaptureHandler(logging.Handler):
    """Collect emitted log records for assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_generate_api_key_length() -> None:
    """Verify generate_api_key returns a key of the requested length."""
    # Given a requested length
    # When a key is generated
    key = generate_api_key(length=40)
    # Then it has that length
    assert len(key) == 40


def test_log_auth_failure_logs_warning_with_correlation() -> None:
    """Verify a rejected auth attempt logs WARNING with request_id, path, and reason."""
    # Given a connection carrying a request id and path
    connection = SimpleNamespace(scope={"state": {"request_id": "req_x"}, "path": "/api/v1/x"})
    logger = logging.getLogger("vapi")
    handler = _CaptureHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)

    # When an auth failure is logged
    try:
        log_auth_failure(connection, "invalid API key")
    finally:
        logger.removeHandler(handler)

    # Then one WARNING record carries the correlation fields and reason
    assert len(handler.records) == 1
    record = handler.records[0]
    assert record.levelno == logging.WARNING
    assert record.request_id == "req_x"
    assert record.path == "/api/v1/x"
    assert record.reason == "invalid API key"


def test_log_auth_failure_handles_missing_state() -> None:
    """Verify the helper does not raise when scope has no state populated."""
    # Given a connection whose scope lacks a state dict
    connection = SimpleNamespace(scope={})
    logger = logging.getLogger("vapi")
    handler = _CaptureHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)

    # When an auth failure is logged
    try:
        log_auth_failure(connection, "missing API key")
    finally:
        logger.removeHandler(handler)

    # Then it still logs, with request_id absent
    assert len(handler.records) == 1
    assert handler.records[0].request_id is None
