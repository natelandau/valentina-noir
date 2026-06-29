"""Tests for after-response hook helpers."""

import json

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
