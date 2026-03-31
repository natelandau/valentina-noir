"""Abstract base model for all TortoiseORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.models import Model
from uuid_utils import uuid7

from vapi.utils.time import time_now

if TYPE_CHECKING:
    from collections.abc import Iterable

    from tortoise.backends.base.client import BaseDBAsyncClient


class BaseModel(Model):
    """Abstract base model providing UUID v7 primary key, timestamps, and archive fields.

    All concrete Tortoise models inherit from this. Archive date management is
    handled via save() override because Tortoise signals don't fire on abstract models.
    """

    id = fields.UUIDField(primary_key=True, default=uuid7)
    date_created = fields.DatetimeField(auto_now_add=True)
    date_modified = fields.DatetimeField(auto_now=True)
    is_archived = fields.BooleanField(default=False)
    archive_date = fields.DatetimeField(null=True)

    class Meta:
        """Tortoise ORM meta options."""

        abstract = True

    async def save(
        self,
        using_db: BaseDBAsyncClient | None = None,
        update_fields: Iterable[str] | None = None,
        force_create: bool = False,  # noqa: FBT001, FBT002
        force_update: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        """Set archive_date when is_archived transitions to True, clear when False."""
        if self.is_archived and self.archive_date is None:
            self.archive_date = time_now()
        elif not self.is_archived:
            self.archive_date = None
        await super().save(
            using_db=using_db,
            update_fields=update_fields,
            force_create=force_create,
            force_update=force_update,
        )
