"""Test the detail_includes helper."""

from enum import StrEnum
from unittest.mock import AsyncMock

import pytest

from vapi.lib.detail_includes import apply_includes

pytestmark = pytest.mark.anyio


class _Inc(StrEnum):
    TRAITS = "traits"
    NOTES = "notes"
    ASSETS = "assets"


_MAP = {
    _Inc.TRAITS: ["traits__trait", "traits__trait__category"],
    _Inc.NOTES: ["notes"],
    _Inc.ASSETS: ["assets"],
}


async def test_apply_includes_none_skips_fetch() -> None:
    """Verify passing None for include does not call fetch_related."""
    # Given an object with a mocked fetch_related
    obj = AsyncMock()

    # When apply_includes is called with no includes
    result = await apply_includes(obj, None, _MAP)

    # Then fetch_related is not called and the set is empty
    obj.fetch_related.assert_not_called()
    assert result == set()


async def test_apply_includes_empty_list_skips_fetch() -> None:
    """Verify an empty include list does not call fetch_related."""
    # Given an object with a mocked fetch_related
    obj = AsyncMock()

    # When apply_includes is called with an empty list
    result = await apply_includes(obj, [], _MAP)

    # Then fetch_related is not called
    obj.fetch_related.assert_not_called()
    assert result == set()


async def test_apply_includes_single_value_prefetches_mapped_relations() -> None:
    """Verify a single include expands to all mapped prefetch strings."""
    # Given an object with a mocked fetch_related
    obj = AsyncMock()

    # When apply_includes is called with one include
    result = await apply_includes(obj, [_Inc.TRAITS], _MAP)

    # Then fetch_related is called once with the two mapped prefetches
    obj.fetch_related.assert_awaited_once_with("traits__trait", "traits__trait__category")
    assert result == {_Inc.TRAITS}


async def test_apply_includes_multiple_values_merges_prefetches() -> None:
    """Verify multiple includes are merged into a single fetch_related call."""
    # Given an object with a mocked fetch_related
    obj = AsyncMock()

    # When apply_includes is called with several includes
    result = await apply_includes(obj, [_Inc.NOTES, _Inc.ASSETS], _MAP)

    # Then fetch_related is called exactly once with the union of prefetch strings
    assert obj.fetch_related.await_count == 1
    called_args = set(obj.fetch_related.await_args.args)
    assert called_args == {"notes", "assets"}
    assert result == {_Inc.NOTES, _Inc.ASSETS}


async def test_apply_includes_dedupes_repeated_values() -> None:
    """Verify duplicate include values are deduplicated into the returned set."""
    # Given an object with a mocked fetch_related
    obj = AsyncMock()

    # When apply_includes is called with duplicate includes
    result = await apply_includes(obj, [_Inc.NOTES, _Inc.NOTES], _MAP)

    # Then the returned set contains one entry and fetch_related is called once
    assert result == {_Inc.NOTES}
    obj.fetch_related.assert_awaited_once_with("notes")
