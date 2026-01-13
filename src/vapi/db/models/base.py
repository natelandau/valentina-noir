"""Base model for all beanie ODM documents."""

from datetime import datetime
from hashlib import sha512

from beanie import (
    Document,
    Insert,
    Replace,
    Save,
    SaveChanges,
    Update,
    before_event,
)
from pydantic import BaseModel, ConfigDict, Field

from vapi.utils.time import time_now


class BaseDocument(Document):
    """Base document for all beanie ODM documents. Implements common fields and functionality."""

    model_config = ConfigDict(str_strip_whitespace=True)

    model_version: int = Field(default=1, exclude=True)
    date_created: datetime = Field(default_factory=time_now)
    date_modified: datetime = Field(default_factory=time_now)
    is_archived: bool = Field(default=False)
    archive_date: datetime | None = None

    @before_event(Insert, Replace, Save, Update, SaveChanges)
    async def update_modified_date(self) -> None:
        """Update the date_modified field."""
        self.date_modified = time_now()

    @before_event(Insert, Replace, Save, Update, SaveChanges)
    async def update_archived_date(self) -> None:
        """Update the archive_date field."""
        self.archive_date = time_now() if self.is_archived and self.archive_date is None else None


class HashedBaseModel(BaseModel):
    """Adds a __hash__ method to Pydantic models without requiring the frozen=True flag.

    Use this model for nested objects within a database document to allow patch operations to work correctly with Litestar's PdytanticDTO.
    """

    def __hash__(self) -> int:
        """Hash the model."""
        return int.from_bytes(
            sha512(
                f"{self.__class__.__qualname__}::{self.model_dump(mode='json')}".encode(
                    "utf-8", errors="ignore"
                )
            ).digest()
        )


class NameDescriptionSubDocument(HashedBaseModel):
    """Name and description base model. Use this for sub-documents that have a name and description."""

    name: str | None = None
    description: str | None = None
