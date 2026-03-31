"""Dictionary DTOs."""

from litestar.plugins.pydantic import PydanticDTO

from vapi.db.models import DictionaryTerm
from vapi.lib.dto import dto_config


class DictionaryTermPostDTO(PydanticDTO[DictionaryTerm]):
    """Dictionary term post DTO."""

    config = dto_config(
        exclude={"id", "date_created", "date_modified", "company_id", "source_type", "source_id"}
    )


class DictionaryTermPatchDTO(PydanticDTO[DictionaryTerm]):
    """Dictionary term patch DTO."""

    config = dto_config(
        exclude={"id", "date_created", "date_modified", "company_id", "source_type", "source_id"},
        partial=True,
    )


class DictionaryTermResponseDTO(PydanticDTO[DictionaryTerm]):
    """Dictionary term response DTO."""

    config = dto_config()
