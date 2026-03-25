"""Document comparison utilities for fixture syncing."""

import json
import re
from enum import Enum
from typing import Any

from beanie import Document
from pydantic import BaseModel

from vapi.constants import PROJECT_ROOT_PATH

FIXTURES_PATH = PROJECT_ROOT_PATH / "src/vapi/db/fixtures"

__all__ = (
    "FIXTURES_PATH",
    "JSONWithCommentsDecoder",
    "document_differs_from_fixture",
    "get_differing_fields",
)


def _normalize_value(value: Any) -> Any:
    """Normalize a value for comparison.

    Converts enums to their values, Pydantic models to dicts, and recursively
    normalizes nested structures.

    Args:
        value (Any): The value to normalize.

    Returns:
        Any: The normalized value suitable for comparison.
    """
    if value is None:
        return None

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, BaseModel):
        return {k: _normalize_value(v) for k, v in value.model_dump().items()}

    if isinstance(value, list):
        return [_normalize_value(item) for item in value]

    if isinstance(value, dict):
        return {k: _normalize_value(v) for k, v in value.items()}

    return value


def _values_equal(model_value: Any, fixture_value: Any) -> bool:
    """Compare two values after normalization.

    Args:
        model_value (Any): The value from the database model.
        fixture_value (Any): The value from the fixture JSON.

    Returns:
        bool: True if values are equal, False otherwise.
    """
    normalized_model = _normalize_value(model_value)
    normalized_fixture = _normalize_value(fixture_value)

    # Handle list of dicts - compare as unordered sets
    if (
        isinstance(normalized_model, list)
        and normalized_model
        and isinstance(normalized_model[0], dict)
    ):
        if not isinstance(normalized_fixture, list) or len(normalized_model) != len(
            normalized_fixture
        ):
            return False

        try:
            model_set = {frozenset(_flatten_dict(d).items()) for d in normalized_model}
            fixture_set = {frozenset(_flatten_dict(d).items()) for d in normalized_fixture}
            return model_set == fixture_set  # noqa: TRY300
        except TypeError:
            return normalized_model == normalized_fixture

    return normalized_model == normalized_fixture


def _flatten_dict(d: dict[str, Any], parent_key: str = "") -> dict[str, Any]:
    """Flatten a nested dictionary for hashable comparison."""
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key).items())
        elif isinstance(v, list):
            items.append(
                (
                    new_key,
                    tuple(_normalize_value(item) if isinstance(item, dict) else item for item in v),
                )
            )
        else:
            items.append((new_key, v))
    return dict(items)


def document_differs_from_fixture[T: Document](document: T, fixture_data: dict[str, Any]) -> bool:
    """Compare a Beanie document against fixture data.

    Only compares fields present in the fixture data. Fields that exist in the
    document but not in the fixture are ignored.

    Args:
        document (T): The Beanie document from the database.
        fixture_data (dict[str, Any]): The corresponding fixture data from JSON.

    Returns:
        bool: True if the document differs from the fixture, False if they match.
    """
    for field_name, fixture_value in fixture_data.items():
        if not hasattr(document, field_name):
            continue

        if not _values_equal(getattr(document, field_name), fixture_value):
            return True

    return False


def get_differing_fields[T: Document](
    document: T, fixture_data: dict[str, Any]
) -> dict[str, tuple[Any, Any]]:
    """Get all fields that differ between a document and fixture data.

    Args:
        document (T): The Beanie document from the database.
        fixture_data (dict[str, Any]): The corresponding fixture data from JSON.

    Returns:
        dict[str, tuple[Any, Any]]: Field names mapped to (document_value, fixture_value).
    """
    differences: dict[str, tuple[Any, Any]] = {}

    for field_name, fixture_value in fixture_data.items():
        if not hasattr(document, field_name):
            continue

        document_value = getattr(document, field_name)
        if not _values_equal(document_value, fixture_value):
            differences[field_name] = (_normalize_value(document_value), fixture_value)

    return differences


class JSONWithCommentsDecoder(json.JSONDecoder):
    """JSON with comments decoder."""

    def __init__(self, **kwgs: Any):
        super().__init__(**kwgs)

    def decode(self, s: str) -> Any:  # type: ignore [override]
        """Decode the JSON with comments."""
        regex = r"""("(?:\\"|[^"])*?")|(\/\*(?:.|\s)*?\*\/|\/\/.*)"""
        s = re.sub(regex, r"\1", s)  # , flags = re.X | re.M)
        return super().decode(s)
