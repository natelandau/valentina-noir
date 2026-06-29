"""Document comparison utilities for fixture syncing."""

import json
import re
from collections.abc import Callable, Iterator
from enum import Enum
from typing import Any, override

from vapi.constants import PROJECT_ROOT_PATH

FIXTURES_PATH = PROJECT_ROOT_PATH / "src/vapi/db/fixtures"

# Matches JSON strings (preserved) and comments (removed)
_COMMENT_RE = re.compile(r"""("(?:\\"|[^"])*?")|(/\*(?:.|\s)*?\*/|//.*)""")

__all__ = (
    "FIXTURES_PATH",
    "JSONWithCommentsDecoder",
    "fixture_key_error",
    "iter_trait_fixtures",
    "needs_update",
)


def iter_trait_fixtures(fixture_data: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Yield every trait dict in parsed traits.json, at both subcategory and category levels.

    Centralizes the section -> category -> [subcategory] -> traits walk so the validation
    and gift-map passes share one traversal instead of each open-coding it. Subcategory
    traits are yielded before category-level traits, matching the gift-map's last-wins order.

    Args:
        fixture_data: The parsed traits.json data.
    """
    for section in fixture_data:
        for category in section.get("categories", []):
            for subcategory in category.get("subcategories", []):
                yield from subcategory.get("traits", [])
            yield from category.get("traits", [])


def fixture_key_error(filename: str, item: Any, exc: KeyError) -> ValueError:
    """Build an actionable error for a fixture entry missing a required key.

    Hand-edited fixtures fail with a bare ``KeyError`` that names neither the
    file nor the offending entry. Wrap them so a malformed fixture points the
    maintainer straight at the file and entry to fix.

    Args:
        filename: The fixture filename being processed.
        item: The fixture entry that triggered the error.
        exc: The original KeyError raised while reading the entry.
    """
    label = item.get("name", item) if isinstance(item, dict) else item
    return ValueError(
        f"{filename}: fixture entry {label!r} is missing required key {exc.args[0]!r}"
    )


def needs_update(instance: Any, defaults: dict[str, Any]) -> bool:
    """Check whether a Tortoise model instance differs from proposed default values.

    Handle enums (compare .value) and FK model instances (compare via _id suffix).

    Args:
        instance: The existing Tortoise model instance.
        defaults: The proposed field values to compare against.

    Returns:
        bool: True if any field in defaults differs from the instance's current value.
    """
    for key, new_value in defaults.items():
        # Compare foreign keys by their raw {field}_id column so diffing never triggers a lazy relation fetch
        id_attr = f"{key}_id"
        if hasattr(instance, id_attr):
            current_id = getattr(instance, id_attr)
            new_id = new_value.pk if hasattr(new_value, "pk") else new_value
            if current_id != new_id:
                return True
            continue

        current = getattr(instance, key, None)

        current_cmp = current.value if isinstance(current, Enum) else current
        new_cmp = new_value.value if isinstance(new_value, Enum) else new_value

        if current_cmp != new_cmp:
            return True

    return False


class JSONWithCommentsDecoder(json.JSONDecoder):
    """JSON decoder that strips single-line and block comments before parsing."""

    @override
    def decode(self, s: str, _w: Callable[..., Any] | None = None) -> Any:
        """Strip // and /* */ comments before parsing so JSONC-authored fixtures load cleanly."""
        s = _COMMENT_RE.sub(r"\1", s)
        if _w is None:
            return super().decode(s)
        return super().decode(s, _w)
