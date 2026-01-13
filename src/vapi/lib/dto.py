"""DTO utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar.dto.config import DTOConfig

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

    from litestar.dto import RenameStrategy

__all__ = ("DTOConfig", "dto_config")


COMMON_EXCLUDES: AbstractSet[str] = {
    "revision_id",
    "model_version",
    "archive_date",
    "is_archived",
}


def dto_config(  # noqa: PLR0913
    *,
    exclude: AbstractSet[str] | None = None,
    include: AbstractSet[str] | None = None,
    rename_fields: dict[str, str] | None = None,
    rename_strategy: RenameStrategy | None = None,
    max_nested_depth: int | None = None,
    partial: bool | None = None,
    forbid_unknown_fields: bool | None = None,
) -> DTOConfig:
    """Configure a DTO class.

    Returns:
        DTOConfig: Configured DTO class
    """
    default_kwargs: dict[str, Any] = {"max_nested_depth": 2}
    default_kwargs["exclude"] = exclude | COMMON_EXCLUDES if exclude else COMMON_EXCLUDES

    if rename_fields:
        default_kwargs["rename_fields"] = rename_fields
    if rename_strategy:
        default_kwargs["rename_strategy"] = rename_strategy
    if max_nested_depth:
        default_kwargs["max_nested_depth"] = max_nested_depth
    if include:
        default_kwargs["include"] = include
    if partial:
        default_kwargs["partial"] = partial
    if forbid_unknown_fields:
        default_kwargs["forbid_unknown_fields"] = forbid_unknown_fields

    return DTOConfig(**default_kwargs)
