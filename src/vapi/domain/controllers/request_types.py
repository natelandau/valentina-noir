"""Constrained field types shared by request Structs across controllers."""

from typing import Annotated

import msgspec

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

__all__ = ("EMAIL_REQUEST_PATTERN", "Email", "Name3to50", "NameMax50", "PersonName")
