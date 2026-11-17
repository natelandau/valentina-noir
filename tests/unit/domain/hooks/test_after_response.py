"""Tests for after-response hook helpers."""

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import msgspec
import pytest

from vapi.domain.hooks import after_response


@pytest.mark.anyio
class TestPostDataUpdateHook:
    """Test post_data_update_hook side-effect suppression."""

    async def test_skips_cache_invalidation_when_resources_unmodified(self, mocker) -> None:
        """Verify a resources_unmodified request still audits but skips the cache flush and bump."""
        # Given mocked side effects and a request flagged as resources_unmodified
        add_audit = mocker.patch.object(after_response, "add_audit_log", autospec=True)
        delete_cache = mocker.patch.object(
            after_response, "delete_response_cache_for_api_key", autospec=True
        )
        company = mocker.patch.object(after_response, "Company")
        request = mocker.MagicMock()
        request.state = SimpleNamespace(resources_unmodified=True)
        request.path_params = {"company_id": "abc"}

        # When the hook runs
        await after_response.post_data_update_hook(request)

        # Then the audit log is written but the cache flush and timestamp bump are skipped
        add_audit.assert_awaited_once_with(request)
        delete_cache.assert_not_awaited()
        company.filter.assert_not_called()

    async def test_invalidates_cache_when_resources_modified(self, mocker) -> None:
        """Verify a normal mutating request flushes the cache and bumps the company timestamp."""
        # Given mocked side effects and a request that did modify resources
        add_audit = mocker.patch.object(after_response, "add_audit_log", autospec=True)
        delete_cache = mocker.patch.object(
            after_response, "delete_response_cache_for_api_key", autospec=True
        )
        delete_company_cache = mocker.patch.object(
            after_response, "delete_response_cache_for_company", autospec=True
        )
        company = mocker.patch.object(after_response, "Company")
        company.filter.return_value.update = mocker.AsyncMock()
        request = mocker.MagicMock()
        request.state = SimpleNamespace()
        request.path_params = {"company_id": "abc"}

        # When the hook runs
        await after_response.post_data_update_hook(request)

        # Then the cache is flushed and the company timestamp is bumped
        add_audit.assert_awaited_once_with(request)
        delete_cache.assert_awaited_once_with(request)
        delete_company_cache.assert_awaited_once_with(request, "abc")
        company.filter.assert_called_once_with(id="abc")
        company.filter.return_value.update.assert_awaited_once()

    async def test_invalidates_cache_when_audit_write_fails(self, mocker) -> None:
        """Verify a failed audit insert still flushes the cache and bumps the company timestamp."""
        # Given an audit write that fails and a request that modified resources
        mocker.patch.object(
            after_response, "add_audit_log", autospec=True, side_effect=ValueError("bad id")
        )
        delete_cache = mocker.patch.object(
            after_response, "delete_response_cache_for_api_key", autospec=True
        )
        delete_company_cache = mocker.patch.object(
            after_response, "delete_response_cache_for_company", autospec=True
        )
        company = mocker.patch.object(after_response, "Company")
        company.filter.return_value.update = mocker.AsyncMock()
        request = mocker.MagicMock()
        request.state = SimpleNamespace()
        request.path_params = {"company_id": "abc"}

        # When the hook runs
        with pytest.raises(ValueError, match="bad id"):
            await after_response.post_data_update_hook(request)

        # Then the cache flush and timestamp bump still happen
        delete_cache.assert_awaited_once_with(request)
        delete_company_cache.assert_awaited_once_with(request, "abc")
        company.filter.return_value.update.assert_awaited_once()

    async def test_invalidates_affected_company_without_company_path_param(self, mocker) -> None:
        """Verify a route without company_id clears the company named in request state."""
        # Given a global-admin style request that names the affected company in state
        mocker.patch.object(after_response, "add_audit_log", autospec=True)
        mocker.patch.object(after_response, "delete_response_cache_for_api_key", autospec=True)
        delete_company_cache = mocker.patch.object(
            after_response, "delete_response_cache_for_company", autospec=True
        )
        company = mocker.patch.object(after_response, "Company")
        company.filter.return_value.update = mocker.AsyncMock()
        request = mocker.MagicMock()
        request.state = SimpleNamespace(affected_company_id="def")
        request.path_params = {"user_id": "u1"}

        # When the hook runs
        await after_response.post_data_update_hook(request)

        # Then the named company's cache is cleared and its timestamp is bumped
        delete_company_cache.assert_awaited_once_with(request, "def")
        company.filter.assert_called_once_with(id="def")
        company.filter.return_value.update.assert_awaited_once()

    async def test_skips_company_invalidation_without_company(self, mocker) -> None:
        """Verify a route with no company path param or state skips the company flush."""
        # Given a request that names no company
        mocker.patch.object(after_response, "add_audit_log", autospec=True)
        mocker.patch.object(after_response, "delete_response_cache_for_api_key", autospec=True)
        delete_company_cache = mocker.patch.object(
            after_response, "delete_response_cache_for_company", autospec=True
        )
        company = mocker.patch.object(after_response, "Company")
        request = mocker.MagicMock()
        request.state = SimpleNamespace()
        request.path_params = {}

        # When the hook runs
        await after_response.post_data_update_hook(request)

        # Then no company cache is cleared
        delete_company_cache.assert_not_awaited()
        company.filter.assert_not_called()


@pytest.fixture
def create(mocker) -> MagicMock:
    """Patch the audit insert and structured-field builder, returning the insert mock."""
    mocker.patch.object(after_response, "build_audit_entry", return_value={})
    return mocker.patch.object(after_response.AuditLog, "create", autospec=True)


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
        await after_response.add_audit_log(_audit_request(mocker, body))

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
        await after_response.add_audit_log(_audit_request(mocker, body))

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
        await after_response.add_audit_log(_audit_request(mocker, body))

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
        await after_response.add_audit_log(_audit_request(mocker, body))

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
        await after_response.add_audit_log(request)

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
        await after_response.add_audit_log(_audit_request(mocker, body))

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
        await after_response.add_audit_log(_audit_request(mocker, body))

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
        await after_response.add_audit_log(_audit_request(mocker, body))

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
        await after_response.add_audit_log(_audit_request(mocker, body))

        # Then the entry is written with no request body
        kwargs = create.call_args.kwargs
        assert kwargs["request_body"] is None
        assert kwargs["request_json"] is None
