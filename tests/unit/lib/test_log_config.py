"""Tests for logging config: stack-trace suppression and the uncaught-exception handler."""

import logging
from types import SimpleNamespace

from vapi.lib.exceptions import ConflictError, NotFoundError
from vapi.lib.log_config import get_logging_config, log_uncaught_exception


class _CaptureHandler(logging.Handler):
    """Collect emitted log records for assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_value_error_is_not_suppressed() -> None:
    """Verify ValueError is no longer suppressed so unhandled ValueErrors get logged."""
    # Given the application logging config
    config = get_logging_config()
    # When inspecting the stack-trace suppression set
    # Then ValueError is absent (a genuine bug should log) while handled client errors remain
    assert ValueError not in config.disable_stack_trace
    assert ConflictError in config.disable_stack_trace
    assert NotFoundError in config.disable_stack_trace
    assert 404 in config.disable_stack_trace


def _raise_key_error() -> None:
    """Raise a KeyError to populate an active exception context for the handler."""
    msg = "boom"
    raise KeyError(msg)


def test_uncaught_exception_handler_logs_with_correlation_and_stashes_type() -> None:
    """Verify the handler logs ERROR with traceback and request id, and records the error type."""
    # Given a scope carrying a request id and authenticated user, inside an active exception
    scope = {
        "type": "http",
        "path": "/boom",
        "state": {"request_id": "req_x"},
        "user": SimpleNamespace(id="dev-1"),
    }
    logger = logging.getLogger("test_uncaught_exception")
    handler = _CaptureHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)

    # When the handler runs for an uncaught error
    try:
        _raise_key_error()
    except KeyError:
        log_uncaught_exception(logger, scope, [])  # type: ignore[arg-type]
    finally:
        logger.removeHandler(handler)

    # Then the error type is stashed for the combined entry to surface
    assert scope["state"]["error_type"] == "KeyError"
    # And exactly one ERROR record carries the traceback and request correlation
    assert len(handler.records) == 1
    record = handler.records[0]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert record.request_id == "req_x"
    assert record.developer_id == "dev-1"
