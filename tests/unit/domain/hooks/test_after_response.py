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

    def test_list_body_passes_through_unchanged(self) -> None:
        """Verify non-dict JSON bodies (e.g. bulk-endpoint arrays) are untouched."""
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
        company.filter.assert_called_once_with(id="abc")
        company.filter.return_value.update.assert_awaited_once()
