"""Gameplay schemas."""

from __future__ import annotations

from beanie import PydanticObjectId  # noqa: TC002
from litestar.plugins.pydantic import PydanticDTO
from pydantic import BaseModel

from vapi.db.models import DiceRoll
from vapi.lib.dto import dto_config


class PostDTO(PydanticDTO[DiceRoll]):
    """Dice roll DTO."""

    config = dto_config(
        exclude={"id", "company_id", "user_id", "date_created", "date_modified", "result"}
    )


class PatchDTO(PydanticDTO[DiceRoll]):
    """Partial dice roll DTO."""

    config = dto_config(
        partial=True,
        exclude={"id", "company_id", "user_id", "date_created", "date_modified", "result"},
    )


class ReturnDTO(PydanticDTO[DiceRoll]):
    """Dice roll DTO."""

    config = dto_config()


class QuickRollDTO(BaseModel):
    """Quick roll DTO."""

    quickroll_id: PydanticObjectId
    character_id: PydanticObjectId
    comment: str | None = None
    difficulty: int = 6
    num_desperation_dice: int = 0
