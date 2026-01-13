"""Character inventory schemas."""

from litestar.plugins.pydantic import PydanticDTO

from vapi.db.models import CharacterInventory
from vapi.lib.dto import dto_config


class PostDTO(PydanticDTO[CharacterInventory]):
    """Inventory item DTO."""

    config = dto_config(exclude={"character_id", "id", "date_created", "date_modified"})


class PatchDTO(PydanticDTO[CharacterInventory]):
    """Partial inventory item DTO."""

    config = dto_config(
        partial=True, exclude={"character_id", "id", "date_created", "date_modified"}
    )


class ReturnDTO(PydanticDTO[CharacterInventory]):
    """Inventory item DTO."""

    config = dto_config()
