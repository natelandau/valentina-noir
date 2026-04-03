"""Unit tests for the utils module for the CLI."""

from __future__ import annotations

import json
from enum import Enum
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from vapi.cli.lib.comparison import (
    JSONWithCommentsDecoder,
    document_differs_from_fixture,
    get_differing_fields,
)
from vapi.cli.lib.sync_counts import SyncCounts
from vapi.cli.lib.trait_syncer import TraitSyncResult

pytestmark = pytest.mark.anyio


class TestSyncCounts:
    """Tests for the SyncCounts dataclass."""

    def test_default_values(self) -> None:
        """Verify SyncCounts initializes with zero counts."""
        # Given: A new SyncCounts instance
        counts = SyncCounts()

        # Then: All values should be zero
        assert counts.created == 0
        assert counts.updated == 0
        assert counts.total == 0

    def test_custom_values(self) -> None:
        """Verify SyncCounts accepts custom values."""
        # Given: Custom values
        counts = SyncCounts(created=5, updated=3, total=10)

        # Then: Values should match
        assert counts.created == 5
        assert counts.updated == 3
        assert counts.total == 10


class TestTraitSyncResult:
    """Tests for the TraitSyncResult dataclass."""

    def test_default_values(self) -> None:
        """Verify TraitSyncResult initializes with default SyncCounts."""
        # Given: A new TraitSyncResult instance
        result = TraitSyncResult()

        # Then: All nested SyncCounts should have zero values
        assert result.sections.created == 0
        assert result.sections.updated == 0
        assert result.sections.total == 0
        assert result.categories.created == 0
        assert result.traits.created == 0

    def test_custom_values(self) -> None:
        """Verify TraitSyncResult accepts custom SyncCounts."""
        # Given: Custom SyncCounts
        sections = SyncCounts(created=1, updated=2, total=3)
        categories = SyncCounts(created=4, updated=5, total=6)
        traits = SyncCounts(created=7, updated=8, total=9)

        # When: Creating TraitSyncResult with custom values
        result = TraitSyncResult(sections=sections, categories=categories, traits=traits)

        # Then: Values should match
        assert result.sections.created == 1
        assert result.categories.total == 6
        assert result.traits.updated == 8


class TestJSONWithCommentsDecoder:
    """Tests for the JSONWithCommentsDecoder class."""

    def test_decode_json_without_comments(self) -> None:
        """Verify decoding standard JSON without comments."""
        # Given: Standard JSON
        json_str = '{"name": "test", "value": 42}'

        # When: Decoding
        result = json.loads(json_str, cls=JSONWithCommentsDecoder)

        # Then: Values should be parsed correctly
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_decode_json_with_single_line_comments(self) -> None:
        """Verify decoding JSON with single-line comments."""
        # Given: JSON with single-line comments
        json_str = """{
            "name": "test", // This is a comment
            "value": 42
        }"""

        # When: Decoding
        result = json.loads(json_str, cls=JSONWithCommentsDecoder)

        # Then: Comments should be stripped
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_decode_json_with_multi_line_comments(self) -> None:
        """Verify decoding JSON with multi-line comments."""
        # Given: JSON with multi-line comments
        json_str = """{
            /* This is a
               multi-line comment */
            "name": "test",
            "value": 42
        }"""

        # When: Decoding
        result = json.loads(json_str, cls=JSONWithCommentsDecoder)

        # Then: Comments should be stripped
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_decode_json_with_mixed_comments(self) -> None:
        """Verify decoding JSON with both comment types."""
        # Given: JSON with both comment types
        json_str = """{
            /* Header comment */
            "name": "test", // inline comment
            "value": 42 /* trailing comment */
        }"""

        # When: Decoding
        result = json.loads(json_str, cls=JSONWithCommentsDecoder)

        # Then: All comments should be stripped
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_decode_preserves_strings_with_slashes(self) -> None:
        """Verify strings containing slashes are preserved."""
        # Given: JSON with strings containing slashes
        json_str = '{"url": "http://example.com/path"}'

        # When: Decoding
        result = json.loads(json_str, cls=JSONWithCommentsDecoder)

        # Then: Strings should be preserved
        assert result["url"] == "http://example.com/path"


class TestDocumentDiffersFromFixture:
    """Tests for the document_differs_from_fixture function."""

    def test_identical_documents(self) -> None:
        """Verify identical documents return False."""
        # Given: A mock document and matching fixture
        document = MagicMock()
        document.name = "Test"
        document.value = 42
        fixture = {"name": "Test", "value": 42}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return False (no difference)
        assert result is False

    def test_differing_string_field(self) -> None:
        """Verify differing string fields return True."""
        # Given: A mock document with different name
        document = MagicMock()
        document.name = "Different"
        document.value = 42
        fixture = {"name": "Test", "value": 42}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return True (difference found)
        assert result is True

    def test_differing_numeric_field(self) -> None:
        """Verify differing numeric fields return True."""
        # Given: A mock document with different value
        document = MagicMock()
        document.name = "Test"
        document.value = 99
        fixture = {"name": "Test", "value": 42}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return True
        assert result is True

    def test_fixture_field_not_in_document(self) -> None:
        """Verify fixture fields not in document are ignored."""
        # Given: A document missing a fixture field
        document = MagicMock(spec=["name"])
        document.name = "Test"
        fixture = {"name": "Test", "missing_field": "value"}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return False (missing fields are skipped)
        assert result is False

    def test_enum_comparison(self) -> None:
        """Verify enum values are compared correctly."""

        # Given: An enum and matching fixture
        class Status(Enum):
            ACTIVE = "active"

        document = MagicMock()
        document.status = Status.ACTIVE
        fixture = {"status": "active"}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return False (enum value matches string)
        assert result is False

    def test_list_comparison(self) -> None:
        """Verify list values are compared correctly."""
        # Given: A document with matching list
        document = MagicMock()
        document.items = ["a", "b", "c"]
        fixture = {"items": ["a", "b", "c"]}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return False
        assert result is False

    def test_list_comparison_different(self) -> None:
        """Verify different lists return True."""
        # Given: A document with different list
        document = MagicMock()
        document.items = ["a", "b", "c"]
        fixture = {"items": ["a", "b", "d"]}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return True
        assert result is True

    def test_pydantic_model_comparison(self) -> None:
        """Verify Pydantic models are compared correctly."""

        # Given: A Pydantic model in the document
        class SubModel(BaseModel):
            field: str

        document = MagicMock()
        document.sub = SubModel(field="value")
        fixture = {"sub": {"field": "value"}}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return False
        assert result is False

    def test_none_comparison(self) -> None:
        """Verify None values are compared correctly."""
        # Given: A document with None value
        document = MagicMock()
        document.optional = None
        fixture = {"optional": None}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return False
        assert result is False


class TestGetDifferingFields:
    """Tests for the get_differing_fields function."""

    def test_no_differences(self) -> None:
        """Verify no differences returns empty dict."""
        # Given: A matching document and fixture
        document = MagicMock()
        document.name = "Test"
        document.value = 42
        fixture = {"name": "Test", "value": 42}

        # When: Getting differences
        result = get_differing_fields(document, fixture)

        # Then: Should return empty dict
        assert result == {}

    def test_single_difference(self) -> None:
        """Verify single difference is returned correctly."""
        # Given: A document with one different field
        document = MagicMock()
        document.name = "Different"
        document.value = 42
        fixture = {"name": "Test", "value": 42}

        # When: Getting differences
        result = get_differing_fields(document, fixture)

        # Then: Should contain only the differing field
        assert len(result) == 1
        assert "name" in result
        assert result["name"] == ("Different", "Test")

    def test_multiple_differences(self) -> None:
        """Verify multiple differences are returned correctly."""
        # Given: A document with multiple different fields
        document = MagicMock()
        document.name = "Different"
        document.value = 99
        fixture = {"name": "Test", "value": 42}

        # When: Getting differences
        result = get_differing_fields(document, fixture)

        # Then: Should contain all differing fields
        assert len(result) == 2
        assert result["name"] == ("Different", "Test")
        assert result["value"] == (99, 42)

    def test_missing_document_field(self) -> None:
        """Verify missing document fields are skipped."""
        # Given: A document missing a fixture field
        document = MagicMock(spec=["name"])
        document.name = "Test"
        fixture = {"name": "Test", "missing_field": "value"}

        # When: Getting differences
        result = get_differing_fields(document, fixture)

        # Then: Missing field should not appear in differences
        assert "missing_field" not in result
        assert result == {}

    def test_enum_difference(self) -> None:
        """Verify enum differences are normalized."""

        # Given: An enum with different value
        class Status(Enum):
            ACTIVE = "active"

        document = MagicMock()
        document.status = Status.ACTIVE
        fixture = {"status": "inactive"}

        # When: Getting differences
        result = get_differing_fields(document, fixture)

        # Then: Should show normalized enum value
        assert result["status"] == ("active", "inactive")
