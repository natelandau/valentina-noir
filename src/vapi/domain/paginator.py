"""Paginators."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

__all__ = ("OffsetPagination",)


@dataclass
class OffsetPagination[T]:
    """Container for data returned using limit/offset pagination.

    Args:
        items: List of data being sent as part of the response.
        limit: Maximal number of items to send.
        offset: Offset from the beginning of the query.
        total: Total number of items.
    """

    __slots__ = ("items", "limit", "offset", "total")

    items: Sequence[T]
    limit: int
    offset: int
    total: int
