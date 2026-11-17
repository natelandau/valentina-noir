"""Constrained field types shared by request Structs across controllers."""

from typing import Annotated

import msgspec

from vapi.constants import (
    MAX_CHARACTER_AGE,
    MAX_LONG_TEXT_LENGTH,
    MAX_TRAIT_VALUE,
    MAX_URL_LENGTH,
    MAX_VAMPIRE_GENERATION,
    MIN_VAMPIRE_GENERATION,
)
from vapi.db.sql_models.validators import EMAIL_PATTERN

# The model strips whitespace before validate_email_format runs, so the outer \s* keeps
# padded addresses valid.
EMAIL_REQUEST_PATTERN = rf"^\s*{EMAIL_PATTERN.removeprefix('^').removesuffix('$')}\s*$"

Email = Annotated[str, msgspec.Meta(pattern=EMAIL_REQUEST_PATTERN, max_length=255)]
Name3to50 = Annotated[str, msgspec.Meta(min_length=3, max_length=50)]
# Fields the model stores as null when empty take NameMax50, not a minimum, so an empty
# string still clears them.
NameMax50 = Annotated[str, msgspec.Meta(max_length=50)]
PersonName = Annotated[str, msgspec.Meta(min_length=2, max_length=50)]
LongText = Annotated[str, msgspec.Meta(max_length=MAX_LONG_TEXT_LENGTH)]
LongText3 = Annotated[str, msgspec.Meta(min_length=3, max_length=MAX_LONG_TEXT_LENGTH)]
Url = Annotated[str, msgspec.Meta(max_length=MAX_URL_LENGTH)]
# Blocks javascript:, data: and other schemes a client might render as a clickable link.
HttpUrl = Annotated[str, msgspec.Meta(pattern=r"^(?i:https?)://\S+$", max_length=MAX_URL_LENGTH)]
Age = Annotated[int, msgspec.Meta(ge=0, le=MAX_CHARACTER_AGE)]
Generation = Annotated[int, msgspec.Meta(ge=MIN_VAMPIRE_GENERATION, le=MAX_VAMPIRE_GENERATION)]
TraitScore = Annotated[int, msgspec.Meta(ge=0, le=MAX_TRAIT_VALUE)]

__all__ = (
    "EMAIL_REQUEST_PATTERN",
    "Age",
    "Email",
    "Generation",
    "HttpUrl",
    "LongText",
    "LongText3",
    "Name3to50",
    "NameMax50",
    "PersonName",
    "TraitScore",
    "Url",
)
