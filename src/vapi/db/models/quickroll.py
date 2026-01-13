"""Quick roll model."""

from typing import Annotated, ClassVar

from beanie import PydanticObjectId
from pydantic import Field

from vapi.db.models.base import BaseDocument


class QuickRoll(BaseDocument):
    """Quick roll model."""

    name: Annotated[str, Field(min_length=3, max_length=50)]
    description: Annotated[str | None, Field(min_length=3, default=None)]

    user_id: PydanticObjectId

    trait_ids: list[PydanticObjectId] = Field(default_factory=list)

    class Settings:
        """Settings for the QuickRoll model."""

        indexes: ClassVar[list[str]] = ["user_id"]
