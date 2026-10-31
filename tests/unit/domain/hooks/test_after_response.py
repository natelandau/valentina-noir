"""Tests for after-response hook helpers."""

import json
from types import SimpleNamespace

import pytest

from vapi.domain.hooks import after_response
from vapi.domain.hooks.after_response import _apply_redactions


class TestApplyRedactions:
    """Test _apply_redactions."""

    def test_redacts_top_level_keys_in_dict_body(self) -> None:
        """Verify sensitive top-level keys are replaced in dict bodies."""
        # Given a dict request body containing a sensitive field
        request_json = {"provider": "apple", "token": "live-credential"}
        request_body = json.dumps(request_json)

        # When redactions are applied
        body, parsed = _apply_redactions(
            request_body=request_body,
            request_json=request_json,
            redact_fields=["token"],
        )

        # Then the sensitive value is replaced and the raw body stays consistent
        assert parsed == {"provider": "apple", "token": "[REDACTED]"}
        assert body is not None
        assert "live-credential" not in body

    def test_list_body_without_sensitive_keys_passes_through_unchanged(self) -> None:
        """Verify array bodies (e.g. bulk-endpoint arrays) with no sensitive keys are untouched."""
        # Given a list request body, as posted by bulk endpoints
        request_json = [{"trait_id": "abc", "value": 3}]
        request_body = json.dumps(request_json)

        # When redactions are applied
        body, parsed = _apply_redactions(
            request_body=request_body,
            request_json=request_json,
            redact_fields=["token"],
        )

        # Then the body is returned unchanged without raising
        assert body == request_body
        assert parsed == request_json

    def test_redacts_keys_in_nested_objects(self) -> None:
        """Verify sensitive keys inside nested objects are replaced."""
        # Given a body with a credential nested two levels deep
        request_json = {"provider": "apple", "auth": {"meta": {"secret": "s3cr3t"}, "ok": 1}}
        request_body = json.dumps(request_json)

        # When redactions are applied
        body, parsed = _apply_redactions(
            request_body=request_body,
            request_json=request_json,
            redact_fields=["secret"],
        )

        # Then the nested value is replaced and the raw body no longer carries it
        assert parsed == {"provider": "apple", "auth": {"meta": {"secret": "[REDACTED]"}, "ok": 1}}
        assert body is not None
        assert "s3cr3t" not in body

    def test_redacts_keys_inside_array_bodies(self) -> None:
        """Verify sensitive keys in objects inside arrays, including nested arrays, are replaced."""
        # Given an array body whose items carry credentials at different depths
        request_json = [
            {"name": "a", "token": "t1"},
            {"name": "b", "items": [{"api_key": "k1"}, "plain"]},
        ]
        request_body = json.dumps(request_json)

        # When redactions are applied
        body, parsed = _apply_redactions(
            request_body=request_body,
            request_json=request_json,
            redact_fields=["token", "api_key"],
        )

        # Then every sensitive value is replaced and other values are kept
        assert parsed == [
            {"name": "a", "token": "[REDACTED]"},
            {"name": "b", "items": [{"api_key": "[REDACTED]"}, "plain"]},
        ]
        assert body is not None
        assert "t1" not in body
        assert "k1" not in body

    def test_redacts_whole_value_of_sensitive_key(self) -> None:
        """Verify a sensitive key holding an object is replaced as a whole."""
        # Given a sensitive key whose value is itself an object
        request_json = {"secret": {"inner": "value"}}

        # When redactions are applied
        _, parsed = _apply_redactions(
            request_body=json.dumps(request_json),
            request_json=request_json,
            redact_fields=["secret"],
        )

        # Then the whole value is redacted
        assert parsed == {"secret": "[REDACTED]"}

    def test_none_body_passes_through_unchanged(self) -> None:
        """Verify non-JSON bodies are untouched."""
        # Given a request with no parseable JSON body
        request_body = "raw-bytes"

        # When redactions are applied
        body, parsed = _apply_redactions(
            request_body=request_body,
            request_json=None,
            redact_fields=["token"],
        )

        # Then the body is returned unchanged
        assert body == "raw-bytes"
        assert parsed is None


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
