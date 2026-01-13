"""Validation utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from pydantic import ValidationError as PydanticValidationError


def raise_from_pydantic_validation_error(error: PydanticValidationError) -> None:
    """Raise a ValidationError from a PydanticValidationError."""
    raise ValidationError(
        invalid_parameters=[{"field": e["loc"], "message": e["msg"]} for e in error.errors()]
    ) from error
