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

_ARCHIVE_FIELDS = frozenset({"is_archived", "archive_date", "archive_batch_id"})


def new_uuid() -> UUID:
    """Mint a time-ordered uuid7 as a stdlib UUID.

    uuid7() returns a uuid_utils.UUID, which compares unequal to the stdlib UUID
    Postgres reads back. Tortoise matches prefetched rows to their parent in Python
    by primary key, so an unconverted id makes fetch_related silently return nothing
    on instances that were never refetched.
    """
    return UUID(str(uuid7()))


class BaseModel(Model):
    """Abstract base model providing UUID v7 primary key, timestamps, and archive fields.

    All concrete Tortoise models inherit from this. The save() override handles three
    concerns that Tortoise doesn't natively support: whitespace stripping on all string
    fields, empty-string-to-None conversion on opted-in nullable fields, and archive
    stamp management (keeping archive_date and archive_batch_id in sync with
    is_archived). These run before super().save() which triggers field validators.
    """

    id = fields.UUIDField(primary_key=True, default=new_uuid)
    date_created = fields.DatetimeField(auto_now_add=True)
    date_modified = fields.DatetimeField(auto_now=True)
    is_archived = fields.BooleanField(default=False)
    archive_date = fields.DatetimeField(null=True)
    archive_batch_id = fields.UUIDField(null=True, db_index=True)

    _empty_string_to_none_fields: ClassVar[frozenset[str]] = frozenset()
    # is_archived as last read from or written to the database; None when never loaded
    _stored_is_archived: bool | None = None

    class Meta:
        """Tortoise ORM meta options."""

        abstract = True

    @classmethod
    def _init_from_db(cls, **kwargs: object) -> BaseModel:
        instance = super()._init_from_db(**kwargs)
        # A partial (.only()) load may omit the column, so read the instance dict
        instance._stored_is_archived = vars(instance).get("is_archived")  # noqa: SLF001
        return instance

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

    async def lock_for_update(self, **filters: object) -> bool:
        """Lock this row and reload it from the database, if it still matches ``filters``.

        Call inside a transaction before a partial save that must act on the committed
        row rather than the copy loaded earlier in the request, so concurrent changes
        to other columns are neither overwritten nor misread.

        Args:
            **filters: Extra conditions the row must meet, such as ``is_archived=False``.

        Returns:
            True when the row matched and is now locked and reloaded, False otherwise.
        """
        # A full-row model query keeps FOR UPDATE; exists() and values_list() silently drop it
        locked = await type(self).filter(id=self.id, **filters).select_for_update().first()
        if locked is None:
            return False
        for field_name in self._meta.db_fields:
            setattr(self, field_name, getattr(locked, field_name))
        self._stored_is_archived = locked.is_archived
        return True

    @staticmethod
    def _with_stamp_fields(update_fields: Iterable[str]) -> list[str]:
        """Add the stamp columns a partial save must write alongside the named fields.

        Callers name only the fields they changed, so ``date_modified`` and, when the
        archive flag changes, the archive stamps are added here to keep them in step.
        Duplicates are dropped because Postgres rejects a column assigned twice.
        """
        names = dict.fromkeys(update_fields)
        names["date_modified"] = None
        if "is_archived" in names:
            names["archive_date"] = None
            names["archive_batch_id"] = None
        return list(names)

    async def save(
        self,
        using_db: BaseDBAsyncClient | None = None,
        update_fields: Iterable[str] | None = None,
        force_create: bool = False,  # noqa: FBT001, FBT002
        force_update: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        """Strip whitespace, convert empty strings to None, and manage archive stamps (date and batch id).

        A full-row save of a loaded row writes the archive columns only when the caller
        changed ``is_archived`` on the instance, so a stale copy cannot undo an archive
        (such as a parent delete's cascade) committed after it was loaded.
        """
        self.normalize_string_fields()

        # Invariant: archived rows always carry both a date and a batch id; a
        # single-row archive is a self-contained batch of one. The DB trigger
        # (see migration) is the cross-path backstop; this keeps ORM saves correct.
        if self.is_archived:
            if self.archive_date is None:
                self.archive_date = time_now()
            if self.archive_batch_id is None:
                self.archive_batch_id = new_uuid()
        else:
            self.archive_date = None
            self.archive_batch_id = None
        if update_fields is not None:
            update_fields = self._with_stamp_fields(update_fields)
        elif (
            self._saved_in_db and not force_create and self.is_archived == self._stored_is_archived
        ):
            update_fields = [
                name
                for name in self._meta.db_fields
                if name not in _ARCHIVE_FIELDS and name != self._meta.pk_attr
            ]
        await super().save(
            using_db=using_db,
            update_fields=update_fields,
            force_create=force_create,
            force_update=force_update,
        )
        self._stored_is_archived = self.is_archived
