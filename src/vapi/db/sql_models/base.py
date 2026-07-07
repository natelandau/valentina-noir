"""Abstract base model for all TortoiseORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

from tortoise import fields
from tortoise.fields.data import CharEnumFieldInstance, CharField, TextField
from tortoise.models import Model
from uuid_utils import uuid7

from vapi.utils.time import time_now

if TYPE_CHECKING:
    from collections.abc import Iterable

    from tortoise.backends.base.client import BaseDBAsyncClient


class BaseModel(Model):
    """Abstract base model providing UUID v7 primary key, timestamps, and archive fields.

    All concrete Tortoise models inherit from this. The save() override handles three
    concerns that Tortoise doesn't natively support: whitespace stripping on all string
    fields, empty-string-to-None conversion on opted-in nullable fields, and archive
    stamp management (keeping archive_date and archive_batch_id in sync with
    is_archived). These run before super().save() which triggers field validators.
    """

    id = fields.UUIDField(primary_key=True, default=uuid7)
    date_created = fields.DatetimeField(auto_now_add=True)
    date_modified = fields.DatetimeField(auto_now=True)
    is_archived = fields.BooleanField(default=False)
    archive_date = fields.DatetimeField(null=True)
    archive_batch_id = fields.UUIDField(null=True, db_index=True)

    _empty_string_to_none_fields: ClassVar[frozenset[str]] = frozenset()

    class Meta:
        """Tortoise ORM meta options."""

        abstract = True

    def normalize_string_fields(self) -> None:
        """Strip whitespace on string fields and blank opted-in nullable fields to None.

        save() applies this automatically. bulk_create bypasses save() entirely, so
        callers building instances for a bulk insert (the seed cold-start fast path)
        must invoke this first to keep stored values identical to the per-row path.
        """
        # Strip whitespace on all string fields (skip enum fields to preserve enum instances)
        for field_name, field_obj in self._meta.fields_map.items():
            if isinstance(field_obj, CharEnumFieldInstance):
                continue
            if isinstance(field_obj, (CharField, TextField)):
                value = getattr(self, field_name, None)
                if isinstance(value, str):
                    setattr(self, field_name, value.strip())

        # Convert empty strings to None for opted-in nullable fields
        for field_name in self._empty_string_to_none_fields:
            value = getattr(self, field_name, None)
            if isinstance(value, str) and value == "":
                setattr(self, field_name, None)

    async def save(
        self,
        using_db: BaseDBAsyncClient | None = None,
        update_fields: Iterable[str] | None = None,
        force_create: bool = False,  # noqa: FBT001, FBT002
        force_update: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        """Strip whitespace, convert empty strings to None, and manage archive stamps (date and batch id)."""
        self.normalize_string_fields()

        # Invariant: archived rows always carry both a date and a batch id; a
        # single-row archive is a self-contained batch of one. The DB trigger
        # (see migration) is the cross-path backstop; this keeps ORM saves correct.
        if self.is_archived:
            if self.archive_date is None:
                self.archive_date = time_now()
            if self.archive_batch_id is None:
                # uuid7() returns a uuid_utils.UUID; convert to the stdlib type
                # the UUIDField expects so ORM saves match the DB column type.
                self.archive_batch_id = UUID(str(uuid7()))
        else:
            self.archive_date = None
            self.archive_batch_id = None
        await super().save(
            using_db=using_db,
            update_fields=update_fields,
            force_create=force_create,
            force_update=force_update,
        )
