"""Document comparison utilities for fixture syncing."""

import json
import re
from enum import Enum
from typing import Any

from vapi.constants import PROJECT_ROOT_PATH

FIXTURES_PATH = PROJECT_ROOT_PATH / "src/vapi/db/fixtures"

# Matches JSON strings (preserved) and comments (removed)
_COMMENT_RE = re.compile(r"""("(?:\\"|[^"])*?")|(\/\*(?:.|\s)*?\*\/|\/\/.*)""")

__all__ = (
    "FIXTURES_PATH",
    "JSONWithCommentsDecoder",
    "needs_update",
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
        # FK fields: Tortoise stores the raw ID as {field}_id
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

    def decode(self, s: str) -> Any:  # type: ignore [override]
        """Decode JSON after stripping comments."""
        s = _COMMENT_RE.sub(r"\1", s)
        return super().decode(s)
