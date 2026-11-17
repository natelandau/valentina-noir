"""Paginators."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, TypeVar

from litestar.params import Parameter

from vapi.constants import MAX_PAGINATION_OFFSET, REFERENCE_MAX_LIMIT

T = TypeVar("T")

__all__ = ("Offset", "OffsetPagination", "ReferenceLimit")

# Reference (catalog) endpoints serve bounded, slowly-changing seed data, so they allow a
# higher page size than the standard le=100 cap. This lets clients fetch a whole catalog
# (e.g. all blueprint traits) in a single request instead of enumerating many pages.
ReferenceLimit = Annotated[int, Parameter(ge=0, le=REFERENCE_MAX_LIMIT)]
Offset = Annotated[int, Parameter(ge=0, le=MAX_PAGINATION_OFFSET)]


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
