"""Unit tests for RequestIdMiddleware."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from vapi.constants import REQUEST_ID_HEADER, REQUEST_ID_STATE_KEY

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


def _make_scope() -> dict[str, Any]:
    """Create a minimal ASGI HTTP scope for testing."""
    return {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/test",
        "headers": [],
        "state": {},
    }


async def _collect_response_headers(
    middleware_handle: Any, scope: dict[str, Any]
) -> dict[str, str]:
    """Run middleware and collect response headers from the send wrapper."""
    captured_headers: dict[str, str] = {}

    async def mock_next_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})

    receive = AsyncMock()

    sent_messages: list[dict[str, Any]] = []

    async def capturing_send(message: dict[str, Any]) -> None:
        sent_messages.append(message)

    await middleware_handle(scope, receive, capturing_send, mock_next_app)

    for msg in sent_messages:
        if msg["type"] == "http.response.start":
            for raw_key, raw_value in msg.get("headers", []):
                header_name = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
                header_value = raw_value.decode() if isinstance(raw_value, bytes) else raw_value
                captured_headers[header_name] = header_value

    return captured_headers


class TestRequestIdMiddlewareGeneration:
    """Test request ID generation and scope storage."""

    async def test_generates_request_id_on_scope(self) -> None:
        """Verify middleware stores a request ID in scope state."""
        from vapi.middleware.request_id import RequestIdMiddleware

        # Given a fresh HTTP scope
        scope = _make_scope()
        middleware = RequestIdMiddleware()

        # When the middleware handles the request
        async def mock_next_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        await middleware.handle(scope, AsyncMock(), AsyncMock(), mock_next_app)

        # Then a request ID is stored in scope state
        assert REQUEST_ID_STATE_KEY in scope["state"]
        assert scope["state"][REQUEST_ID_STATE_KEY].startswith("req_")

    async def test_request_id_format(self) -> None:
        """Verify request ID has correct prefix and reasonable length."""
        from vapi.middleware.request_id import RequestIdMiddleware

        # Given a fresh HTTP scope
        scope = _make_scope()
        middleware = RequestIdMiddleware()

        # When the middleware handles the request
        async def mock_next_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        await middleware.handle(scope, AsyncMock(), AsyncMock(), mock_next_app)

        # Then the ID has the correct format
        request_id = scope["state"][REQUEST_ID_STATE_KEY]
        assert request_id.startswith("req_")
        assert 20 <= len(request_id) <= 30

    async def test_unique_ids_per_request(self) -> None:
        """Verify two requests produce different IDs."""
        from vapi.middleware.request_id import RequestIdMiddleware

        middleware = RequestIdMiddleware()

        async def mock_next_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        # Given two separate requests
        scope1 = _make_scope()
        scope2 = _make_scope()

        # When both are handled
        await middleware.handle(scope1, AsyncMock(), AsyncMock(), mock_next_app)
        await middleware.handle(scope2, AsyncMock(), AsyncMock(), mock_next_app)

        # Then the IDs are different
        assert scope1["state"][REQUEST_ID_STATE_KEY] != scope2["state"][REQUEST_ID_STATE_KEY]


class TestRequestIdMiddlewareResponseHeader:
    """Test X-Request-Id response header injection."""

    async def test_header_set_on_response(self) -> None:
        """Verify X-Request-Id header is present in the response."""
        from vapi.middleware.request_id import RequestIdMiddleware

        # Given a fresh HTTP scope
        scope = _make_scope()
        middleware = RequestIdMiddleware()

        # When the middleware handles the request
        headers = await _collect_response_headers(middleware.handle, scope)

        # Then X-Request-Id header is present and matches scope state
        # MutableScopeHeaders lowercases header names per HTTP spec
        header_key = REQUEST_ID_HEADER.lower()
        assert header_key in headers
        assert headers[header_key] == scope["state"][REQUEST_ID_STATE_KEY]

    async def test_header_value_matches_scope_state(self) -> None:
        """Verify the response header value matches the scope-stored ID."""
        from vapi.middleware.request_id import RequestIdMiddleware

        # Given a fresh HTTP scope
        scope = _make_scope()
        middleware = RequestIdMiddleware()

        # When the middleware handles the request
        headers = await _collect_response_headers(middleware.handle, scope)

        # Then the header and scope values are identical
        header_key = REQUEST_ID_HEADER.lower()
        assert headers[header_key] == scope["state"][REQUEST_ID_STATE_KEY]

    async def test_non_response_messages_passed_through(self) -> None:
        """Verify non-response-start messages are not modified."""
        from vapi.middleware.request_id import RequestIdMiddleware

        # Given a fresh HTTP scope
        scope = _make_scope()
        middleware = RequestIdMiddleware()
        sent_messages: list[dict[str, Any]] = []

        async def mock_next_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"hello"})

        async def capturing_send(message: dict[str, Any]) -> None:
            sent_messages.append(message)

        # When the middleware handles the request
        await middleware.handle(scope, AsyncMock(), capturing_send, mock_next_app)

        # Then body messages are passed through unchanged
        body_msg = [m for m in sent_messages if m["type"] == "http.response.body"]
        assert len(body_msg) == 1
        assert body_msg[0]["body"] == b"hello"


class TestRequestIdInErrorResponses:
    """Test request ID inclusion in RFC 9457 error response bodies."""

    async def test_request_id_in_error_body(self) -> None:
        """Verify request_id appears in HTTPError response body."""
        from vapi.lib.exceptions import NotFoundError

        # Given a request with a known request ID in scope state
        request_id = "req_test123abc"
        mock_request = MagicMock()
        mock_request.scope = {"state": {REQUEST_ID_STATE_KEY: request_id}}
        mock_request.url = "http://localhost/api/v1/test"

        # When an error response is generated
        error = NotFoundError(detail="Resource not found")
        response = error.to_response(mock_request)

        # Then the response body includes the request_id
        assert response.content["request_id"] == request_id

    async def test_error_body_without_request_id_in_scope(self) -> None:
        """Verify error response works when no request ID is in scope."""
        from vapi.lib.exceptions import NotFoundError

        # Given a request with no request ID in scope state
        mock_request = MagicMock()
        mock_request.scope = {"state": {}}
        mock_request.url = "http://localhost/api/v1/test"

        # When an error response is generated
        error = NotFoundError(detail="Resource not found")
        response = error.to_response(mock_request)

        # Then the response body does not include request_id
        assert "request_id" not in response.content

    async def test_request_id_in_validation_error_body(self) -> None:
        """Verify request_id appears in validation error response body."""
        from vapi.lib.exceptions import ValidationError

        # Given a request with a known request ID in scope state
        request_id = "req_validation456"
        mock_request = MagicMock()
        mock_request.scope = {"state": {REQUEST_ID_STATE_KEY: request_id}}
        mock_request.url = "http://localhost/api/v1/test"
        mock_request.headers = MagicMock()
        mock_request.headers.get = MagicMock(return_value=None)

        # When a validation error response is generated
        error = ValidationError(detail="Validation failed")
        response = error.to_response(mock_request)

        # Then the response body includes the request_id
        assert response.content["request_id"] == request_id


def _make_audit_log_request(scope_state: dict[str, Any] | None = None) -> MagicMock:
    """Create a mock request for audit log tests."""
    mock_request = MagicMock()
    mock_request.scope = {"state": scope_state or {}}
    mock_request.headers = MagicMock()
    mock_request.headers.get = MagicMock(return_value="application/json")
    mock_request.user = MagicMock()
    mock_request.user.id = "developer123"
    mock_request.method = "POST"
    mock_request.url = "http://localhost/api/v1/test"
    mock_request.route_handler = MagicMock()
    mock_request.route_handler.__str__ = MagicMock(return_value="handler_str")
    mock_request.route_handler.handler_name = "create_thing"
    mock_request.route_handler.name = "create_thing"
    mock_request.route_handler.summary = "Create a thing"
    mock_request.route_handler.operation_id = "create_thing"
    mock_request.path_params = {}
    mock_request.query_params = {}
    mock_request.body = AsyncMock(return_value=b"{}")
    mock_request.json = AsyncMock(return_value={})
    return mock_request


class TestRequestIdInAuditLog:
    """Test request ID inclusion in audit log records."""

    async def test_audit_log_receives_request_id(self, mocker: MockerFixture) -> None:
        """Verify add_audit_log passes request_id to AuditLog constructor."""
        # Given a mock request with a known request ID
        request_id = "req_audit789xyz"
        mock_request = _make_audit_log_request({REQUEST_ID_STATE_KEY: request_id})

        # Given AuditLog.insert is mocked
        mock_audit_log_cls = mocker.patch("vapi.db.models.AuditLog")
        mock_instance = MagicMock()
        mock_instance.insert = AsyncMock()
        mock_audit_log_cls.return_value = mock_instance

        # When add_audit_log is called
        from vapi.domain.hooks.after_response import add_audit_log

        await add_audit_log(mock_request)

        # Then AuditLog is created with the request_id
        call_kwargs = mock_audit_log_cls.call_args
        assert call_kwargs.kwargs.get("request_id") == request_id

    async def test_audit_log_without_request_id(self, mocker: MockerFixture) -> None:
        """Verify add_audit_log handles missing request_id gracefully."""
        # Given a mock request with no request ID in scope
        mock_request = _make_audit_log_request()

        # Given AuditLog.insert is mocked
        mock_audit_log_cls = mocker.patch("vapi.db.models.AuditLog")
        mock_instance = MagicMock()
        mock_instance.insert = AsyncMock()
        mock_audit_log_cls.return_value = mock_instance

        # When add_audit_log is called
        from vapi.domain.hooks.after_response import add_audit_log

        await add_audit_log(mock_request)

        # Then AuditLog is created with request_id as None
        call_kwargs = mock_audit_log_cls.call_args
        assert call_kwargs.kwargs.get("request_id") is None
