"""Tests for the post-write hook and its middleware."""

import hashlib
import json
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from unittest.mock import MagicMock

import msgspec
import pytest
from litestar.handlers import route

from vapi.constants import SKIP_POST_DATA_UPDATE_OPT_KEY
from vapi.db.sql_models.developer import Developer
from vapi.domain.hooks import post_data_update


@pytest.mark.anyio
class TestPostDataUpdateHook:
    """Test post_data_update_hook side-effect suppression."""

    async def test_skips_cache_invalidation_when_resources_unmodified(self, mocker) -> None:
        """Verify a resources_unmodified request still audits but skips the cache flush and bump."""
        # Given mocked side effects and a request flagged as resources_unmodified
        add_audit = mocker.patch.object(post_data_update, "add_audit_log", autospec=True)
        delete_cache = mocker.patch.object(
            post_data_update, "delete_response_cache_for_api_key", autospec=True
        )
        company = mocker.patch.object(post_data_update, "Company")
        request = mocker.MagicMock()
        request.state = SimpleNamespace(resources_unmodified=True)
        request.path_params = {"company_id": "abc"}

        # When the hook runs
        await post_data_update.post_data_update_hook(request)

        # Then the audit log is written but the cache flush and timestamp bump are skipped
        add_audit.assert_awaited_once_with(request)
        delete_cache.assert_not_awaited()
        company.filter.assert_not_called()

    async def test_invalidates_cache_when_resources_modified(self, mocker) -> None:
        """Verify a normal mutating request flushes the cache and bumps the company timestamp."""
        # Given mocked side effects and a request that did modify resources
        add_audit = mocker.patch.object(post_data_update, "add_audit_log", autospec=True)
        delete_cache = mocker.patch.object(
            post_data_update, "delete_response_cache_for_api_key", autospec=True
        )
        delete_company_cache = mocker.patch.object(
            post_data_update, "delete_response_cache_for_company", autospec=True
        )
        company = mocker.patch.object(post_data_update, "Company")
        company.filter.return_value.update = mocker.AsyncMock()
        request = mocker.MagicMock()
        request.state = SimpleNamespace()
        request.path_params = {"company_id": "abc"}

        # When the hook runs
        await post_data_update.post_data_update_hook(request)

        # Then the cache is flushed and the company timestamp is bumped
        add_audit.assert_awaited_once_with(request)
        delete_cache.assert_awaited_once_with(request)
        delete_company_cache.assert_awaited_once_with(request, "abc")
        company.filter.assert_called_once_with(id="abc")
        company.filter.return_value.update.assert_awaited_once()

    async def test_runs_audit_then_flush_then_timestamp(self, mocker) -> None:
        """Verify the audit insert precedes the cache flush, and the timestamp moves last."""
        # Given side effects that record the order they ran in
        calls: list[str] = []
        mocker.patch.object(
            post_data_update,
            "add_audit_log",
            autospec=True,
            side_effect=lambda *_: calls.append("audit"),
        )
        mocker.patch.object(
            post_data_update,
            "delete_response_cache_for_api_key",
            autospec=True,
            side_effect=lambda *_: calls.append("api_key"),
        )
        mocker.patch.object(
            post_data_update,
            "delete_response_cache_for_company",
            autospec=True,
            side_effect=lambda *_: calls.append("company"),
        )
        company = mocker.patch.object(post_data_update, "Company")
        company.filter.return_value.update = mocker.AsyncMock(
            side_effect=lambda **_: calls.append("timestamp")
        )
        request = mocker.MagicMock()
        request.state = SimpleNamespace()
        request.path_params = {"company_id": "abc"}

        # When the hook runs
        await post_data_update.post_data_update_hook(request)

        # Then the audit came first and the timestamp bump came last
        assert calls[0] == "audit"
        assert sorted(calls[1:3]) == ["api_key", "company"]
        assert calls[3] == "timestamp"

    async def test_invalidates_cache_when_audit_write_fails(self, mocker) -> None:
        """Verify a failed audit insert still flushes the cache and bumps the company timestamp."""
        # Given an audit write that fails and a request that modified resources
        mocker.patch.object(
            post_data_update, "add_audit_log", autospec=True, side_effect=ValueError("bad id")
        )
        delete_cache = mocker.patch.object(
            post_data_update, "delete_response_cache_for_api_key", autospec=True
        )
        delete_company_cache = mocker.patch.object(
            post_data_update, "delete_response_cache_for_company", autospec=True
        )
        company = mocker.patch.object(post_data_update, "Company")
        company.filter.return_value.update = mocker.AsyncMock()
        request = mocker.MagicMock()
        request.state = SimpleNamespace()
        request.path_params = {"company_id": "abc"}

        # When the hook runs
        with pytest.raises(ValueError, match="bad id"):
            await post_data_update.post_data_update_hook(request)

        # Then the cache flush and timestamp bump still happen
        delete_cache.assert_awaited_once_with(request)
        delete_company_cache.assert_awaited_once_with(request, "abc")
        company.filter.return_value.update.assert_awaited_once()

    async def test_invalidates_affected_company_without_company_path_param(self, mocker) -> None:
        """Verify a route without company_id clears the company named in request state."""
        # Given a global-admin style request that names the affected company in state
        mocker.patch.object(post_data_update, "add_audit_log", autospec=True)
        mocker.patch.object(post_data_update, "delete_response_cache_for_api_key", autospec=True)
        delete_company_cache = mocker.patch.object(
            post_data_update, "delete_response_cache_for_company", autospec=True
        )
        company = mocker.patch.object(post_data_update, "Company")
        company.filter.return_value.update = mocker.AsyncMock()
        request = mocker.MagicMock()
        request.state = SimpleNamespace(affected_company_id="def")
        request.path_params = {"user_id": "u1"}

        # When the hook runs
        await post_data_update.post_data_update_hook(request)

        # Then the named company's cache is cleared and its timestamp is bumped
        delete_company_cache.assert_awaited_once_with(request, "def")
        company.filter.assert_called_once_with(id="def")
        company.filter.return_value.update.assert_awaited_once()

    async def test_skips_company_invalidation_without_company(self, mocker) -> None:
        """Verify a route with no company path param or state skips the company flush."""
        # Given a request that names no company
        mocker.patch.object(post_data_update, "add_audit_log", autospec=True)
        mocker.patch.object(post_data_update, "delete_response_cache_for_api_key", autospec=True)
        delete_company_cache = mocker.patch.object(
            post_data_update, "delete_response_cache_for_company", autospec=True
        )
        company = mocker.patch.object(post_data_update, "Company")
        request = mocker.MagicMock()
        request.state = SimpleNamespace()
        request.path_params = {}

        # When the hook runs
        await post_data_update.post_data_update_hook(request)

        # Then no company cache is cleared
        delete_company_cache.assert_not_awaited()
        company.filter.assert_not_called()


def _app_responding_with(status: int) -> Callable[..., Awaitable[None]]:
    """Build an ASGI app that sends a response with ``status`` and an empty body."""

    async def app(scope, receive, send) -> None:
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    return app


async def _handler() -> None:
    """Stand-in route handler body."""


_DEVELOPER = MagicMock(spec=Developer)


async def _run_middleware(
    app,
    sent: list[dict],
    *,
    method: str = "PATCH",
    opt: dict | None = None,
    user: object = _DEVELOPER,
) -> None:
    """Run the middleware around ``app`` for a route, recording sent messages in ``sent``."""

    async def send(message) -> None:
        sent.append(message)

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "method": method,
        "path": "/",
        "headers": [],
        "state": {},
        "user": user,
        "route_handler": route(path="/", http_method=[method], opt=opt or {})(_handler),
    }
    await post_data_update.PostDataUpdateMiddleware()(app)(scope, receive, send)


@pytest.mark.anyio
class TestPostDataUpdateMiddleware:
    """Test when the middleware runs the hook relative to the response."""

    async def test_runs_hook_before_response_starts(self, mocker) -> None:
        """Verify the hook finishes before the client receives any part of the response."""
        # Given a hook that records how many messages were sent when it ran
        sent: list[dict] = []
        sent_when_hook_ran: list[int] = []

        async def hook(request) -> None:
            sent_when_hook_ran.append(len(sent))

        mocker.patch.object(post_data_update, "post_data_update_hook", side_effect=hook)

        # When a successful write responds
        await _run_middleware(_app_responding_with(200), sent)

        # Then the hook ran once, before the response start was sent
        assert sent_when_hook_ran == [0]
        assert [m["type"] for m in sent] == ["http.response.start", "http.response.body"]

    @pytest.mark.parametrize(
        ("method", "status", "opt", "user"),
        [
            ("PATCH", 400, None, _DEVELOPER),
            ("GET", 200, None, _DEVELOPER),
            ("POST", 201, {SKIP_POST_DATA_UPDATE_OPT_KEY: True}, _DEVELOPER),
            ("POST", 201, None, {"username": "admin"}),
        ],
        ids=["error-response", "read", "opted-out", "basic-auth-user"],
    )
    async def test_skips_hook(
        self, mocker, method: str, status: int, opt: dict | None, user: object
    ) -> None:
        """Verify reads, failed writes, opted-out routes, and non-developers skip the hook."""
        # Given a mocked hook
        hook = mocker.patch.object(post_data_update, "post_data_update_hook", autospec=True)
        sent: list[dict] = []

        # When the request responds
        await _run_middleware(_app_responding_with(status), sent, method=method, opt=opt, user=user)

        # Then the hook did not run and the response was sent
        hook.assert_not_awaited()
        assert sent[0]["status"] == status

    async def test_sends_response_when_hook_fails(self, mocker) -> None:
        """Verify a hook failure is logged and the committed write still gets its response."""
        # Given a hook that raises
        mocker.patch.object(
            post_data_update, "post_data_update_hook", side_effect=RuntimeError("redis down")
        )
        log = mocker.patch.object(post_data_update.logger, "exception")
        sent: list[dict] = []

        # When a successful write responds
        await _run_middleware(_app_responding_with(201), sent, method="POST")

        # Then the failure was logged and the response sent unchanged
        log.assert_called_once()
        assert sent[0]["status"] == 201


@pytest.fixture
def create(mocker) -> MagicMock:
    """Patch the audit insert and structured-field builder, returning the insert mock."""
    mocker.patch.object(post_data_update, "build_audit_entry", return_value={})
    return mocker.patch.object(post_data_update.AuditLog, "create", autospec=True)


def _audit_request(mocker, body: bytes) -> MagicMock:
    """Build a mock JSON request carrying ``body`` for add_audit_log."""
    request = mocker.MagicMock()
    request.headers = {"content-type": "application/json"}
    request.body = mocker.AsyncMock(return_value=body)
    request.state = SimpleNamespace()
    request.scope = {"state": {}}
    request.path_params = {}
    request.query_params = {}
    return request


@pytest.mark.anyio
class TestAddAuditLogBodyCap:
    """Test that add_audit_log persists a bounded summary of the request body."""

    async def test_oversized_body_with_unknown_field_is_not_persisted(self, mocker, create) -> None:
        """Verify an oversized body is stored as its length and hash, not its content."""
        # Given a small valid payload padded with a large unknown field
        payload = {"term": "Abc", "definition": "short", "junk": "x" * 4_000_000}
        body = json.dumps(payload).encode()

        # When the audit entry is written
        await post_data_update.add_audit_log(_audit_request(mocker, body))

        # Then neither stored column carries the body and the summary is bounded
        kwargs = create.call_args.kwargs
        digest = hashlib.sha256(body).hexdigest()
        assert kwargs["request_json"] is None
        assert kwargs["request_body"] == f"[truncated: {len(body)} bytes, sha256={digest}]"

    async def test_body_within_budget_is_persisted(self, mocker, create) -> None:
        """Verify a body within the size budget is stored unchanged."""
        # Given a normal-sized JSON body
        payload = {"term": "Abc", "definition": "y" * 20_000}
        body = json.dumps(payload).encode()

        # When the audit entry is written
        await post_data_update.add_audit_log(_audit_request(mocker, body))

        # Then the raw and parsed bodies are stored in full
        kwargs = create.call_args.kwargs
        assert kwargs["request_json"] == payload
        assert kwargs["request_body"] == body.decode()

    async def test_oversized_body_hash_covers_redacted_body(self, mocker, create) -> None:
        """Verify the stored hash is of the redacted body so it cannot confirm a secret."""
        # Given an oversized body that carries a credential
        payload = {"token": "live-credential", "junk": "x" * 100_000}
        body = json.dumps(payload).encode()

        # When the audit entry is written
        await post_data_update.add_audit_log(_audit_request(mocker, body))

        # Then the hash is of the redacted serialization, not the original bytes
        redacted = msgspec.json.encode({"token": "[REDACTED]", "junk": "x" * 100_000})
        stored = create.call_args.kwargs["request_body"]
        assert hashlib.sha256(redacted).hexdigest() in stored
        assert hashlib.sha256(body).hexdigest() not in stored

    async def test_nul_in_unknown_field_is_replaced(self, mocker, create) -> None:
        """Verify a JSON NUL escape is replaced so PostgreSQL accepts the audit row."""
        # Given a body whose unknown field carries an escaped NUL
        body = b'{"term": "Abc", "junk": "a\\u0000b"}'

        # When the audit entry is written
        await post_data_update.add_audit_log(_audit_request(mocker, body))

        # Then neither stored column holds a NUL
        kwargs = create.call_args.kwargs
        assert kwargs["request_json"] == {"term": "Abc", "junk": "a\ufffdb"}
        assert "\\u0000" not in kwargs["request_body"]
        assert json.loads(kwargs["request_body"]) == kwargs["request_json"]

    async def test_nul_in_query_param_is_replaced(self, mocker, create) -> None:
        """Verify a NUL in a query parameter is replaced so PostgreSQL accepts the audit row."""
        # Given a request whose query string decodes to a NUL
        request = _audit_request(mocker, b"")
        request.query_params = {"junk": "a\x00b"}

        # When the audit entry is written
        await post_data_update.add_audit_log(request)

        # Then the stored query params hold no NUL
        assert create.call_args.kwargs["query_params"] == {"junk": "a\ufffdb"}


@pytest.mark.anyio
class TestAddAuditLogRedaction:
    """Test that add_audit_log never persists credentials or unparsed request text."""

    async def test_redacts_identity_provider_tokens(self, mocker, create) -> None:
        """Verify id_token and access_token values are redacted in the stored body."""
        # Given a body carrying identity-provider tokens
        payload = {"provider": "google", "id_token": "jwt-secret", "access_token": "at-secret"}
        body = json.dumps(payload).encode()

        # When the audit entry is written
        await post_data_update.add_audit_log(_audit_request(mocker, body))

        # Then neither stored column holds a token value
        kwargs = create.call_args.kwargs
        assert kwargs["request_json"] == {
            "provider": "google",
            "id_token": "[REDACTED]",
            "access_token": "[REDACTED]",
        }
        assert "jwt-secret" not in kwargs["request_body"]
        assert "at-secret" not in kwargs["request_body"]

    async def test_redacts_sensitive_keys_regardless_of_case(self, mocker, create) -> None:
        """Verify a sensitive key is redacted when the client sends it in another case."""
        # Given a body with a capitalized credential key
        body = json.dumps({"Password": "hunter2"}).encode()

        # When the audit entry is written
        await post_data_update.add_audit_log(_audit_request(mocker, body))

        # Then the value is redacted
        assert create.call_args.kwargs["request_json"] == {"Password": "[REDACTED]"}
        assert "hunter2" not in create.call_args.kwargs["request_body"]

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param(b'{"token": "live-credential", ', id="malformed-json"),
            pytest.param(b'{"token": "live-credential"}\xff', id="invalid-utf8"),
            pytest.param(b'{"token": "live-credential", "a": "\xff"}', id="invalid-utf8-in-string"),
            pytest.param(b"\xff\xfe", id="not-utf8"),
            pytest.param(b"token=live-credential\x00", id="not-json"),
        ],
    )
    async def test_unparsable_body_is_not_persisted(self, mocker, create, body: bytes) -> None:
        """Verify a body that fails to parse is not stored, so no unredacted text leaks."""
        # Given a body that cannot be parsed as JSON

        # When the audit entry is written
        await post_data_update.add_audit_log(_audit_request(mocker, body))

        # Then the entry is written with no request body
        kwargs = create.call_args.kwargs
        assert kwargs["request_body"] is None
        assert kwargs["request_json"] is None

    @pytest.mark.parametrize("depth", [1_200, 100_000])
    async def test_deeply_nested_body_is_not_persisted(self, mocker, create, depth: int) -> None:
        """Verify a body nested too deeply to process is audited without its content."""
        # Given a credential beside a deeply nested value
        body = b'{"token": "live-credential", "x": ' + b"[" * depth + b"]" * depth + b"}"

        # When the audit entry is written
        await post_data_update.add_audit_log(_audit_request(mocker, body))

        # Then the entry is written with no request body
        kwargs = create.call_args.kwargs
        assert kwargs["request_body"] is None
        assert kwargs["request_json"] is None
