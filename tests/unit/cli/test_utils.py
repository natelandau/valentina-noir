"""Unit tests for the utils module for the CLI."""

from __future__ import annotations

import json

import pytest

from vapi.cli.lib.comparison import JSONWithCommentsDecoder
from vapi.cli.lib.sync_counts import SyncCounts
from vapi.cli.lib.trait_syncer import TraitSyncResult, _validate_trait_value_ranges

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


class TestValidateTraitValueRanges:
    """Tests for _validate_trait_value_ranges."""

    def test_valid_traits_no_error(self) -> None:
        """Verify no error when all traits have valid min/max ranges."""
        # Given: Fixture data with correctly ordered values
        fixture_data = [
            {
                "name": "Section",
                "categories": [
                    {
                        "name": "Cat",
                        "traits": [
                            {"name": "Trait A", "min_value": 0, "max_value": 5},
                            {"name": "Trait B", "min_value": 1, "max_value": 3},
                        ],
                    }
                ],
            }
        ]

        # When/Then: No exception raised
        _validate_trait_value_ranges(fixture_data)

    def test_inverted_category_trait_raises(self) -> None:
        """Verify error when a category-level trait has inverted min/max."""
        # Given: A category trait with min > max
        fixture_data = [
            {
                "name": "Section",
                "categories": [
                    {
                        "name": "Cat",
                        "traits": [
                            {"name": "Bad Trait", "min_value": 5, "max_value": 1},
                        ],
                    }
                ],
            }
        ]

        # When/Then: ValueError is raised mentioning the trait
        with pytest.raises(ValueError, match="Bad Trait"):
            _validate_trait_value_ranges(fixture_data)

    def test_inverted_subcategory_trait_raises(self) -> None:
        """Verify error when a subcategory-level trait has inverted min/max."""
        # Given: A subcategory trait with min > max
        fixture_data = [
            {
                "name": "Section",
                "categories": [
                    {
                        "name": "Cat",
                        "traits": [],
                        "subcategories": [
                            {
                                "name": "Subcat",
                                "traits": [
                                    {"name": "Sub Trait", "min_value": 10, "max_value": 2},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]

        # When/Then: ValueError is raised mentioning the trait
        with pytest.raises(ValueError, match="Sub Trait"):
            _validate_trait_value_ranges(fixture_data)

    def test_multiple_violations_reported(self) -> None:
        """Verify all inverted traits are listed in the error message."""
        # Given: Multiple traits with inverted values across levels
        fixture_data = [
            {
                "name": "Section",
                "categories": [
                    {
                        "name": "Cat",
                        "traits": [
                            {"name": "Bad One", "min_value": 5, "max_value": 1},
                        ],
                        "subcategories": [
                            {
                                "name": "Subcat",
                                "traits": [
                                    {"name": "Bad Two", "min_value": 8, "max_value": 3},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]

        # When/Then: Both violations appear in the error
        with pytest.raises(ValueError, match=r"(?s)Bad One.*Bad Two"):
            _validate_trait_value_ranges(fixture_data)

    def test_defaults_used_when_values_absent(self) -> None:
        """Verify traits without explicit min/max use defaults (0 and 5) and pass."""
        # Given: Traits with no min_value or max_value specified
        fixture_data = [
            {
                "name": "Section",
                "categories": [
                    {
                        "name": "Cat",
                        "traits": [{"name": "Default Trait"}],
                    }
                ],
            }
        ]

        # When/Then: No exception since defaults are min=0, max=5
        _validate_trait_value_ranges(fixture_data)

    def test_equal_min_max_passes(self) -> None:
        """Verify a trait with equal min and max values is valid."""
        # Given: A trait where min equals max
        fixture_data = [
            {
                "name": "Section",
                "categories": [
                    {
                        "name": "Cat",
                        "traits": [{"name": "Fixed Trait", "min_value": 3, "max_value": 3}],
                    }
                ],
            }
        ]

        # When/Then: No exception raised
        _validate_trait_value_ranges(fixture_data)

    def test_empty_fixture_passes(self) -> None:
        """Verify empty fixture data raises no error."""
        # Given: Empty fixture data
        # When/Then: No exception raised
        _validate_trait_value_ranges([])
