"""Dictionary term model — game terminology."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tortoise import fields
from tortoise.exceptions import ValidationError

from vapi.constants import DictionarySourceType
from vapi.db.sql_models.base import BaseModel

if TYPE_CHECKING:
    from collections.abc import Iterable

    from tortoise.backends.base.client import BaseDBAsyncClient

    from vapi.db.sql_models.company import Company


class DictionaryTerm(BaseModel):
    """A game terminology entry with definition and/or link."""

    term = fields.CharField(max_length=50)
    definition = fields.TextField(null=True)
    link = fields.TextField(null=True)
    synonyms: Any = fields.JSONField(default=list)
    source_type = fields.CharEnumField(DictionarySourceType, null=True)
    source_id = fields.UUIDField(null=True)

    company: fields.ForeignKeyRelation[Company] = fields.ForeignKeyField(
        "models.Company",
        related_name="dictionary_terms",
        on_delete=fields.OnDelete.CASCADE,
        null=True,
    )

    class Meta:
        """Tortoise ORM meta options."""

        table = "dictionary_term"

    async def save(
        self,
        using_db: BaseDBAsyncClient | None = None,
        update_fields: Iterable[str] | None = None,
        force_create: bool = False,  # noqa: FBT001, FBT002
        force_update: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        """Validate cross-field constraints before saving."""
        if not self.definition and not self.link:
            msg = "DictionaryTerm must have either a definition or a link."
            raise ValidationError(msg)
        if (self.source_type is None) != (self.source_id is None):
            msg = "source_type and source_id must both be set or both null."
            raise ValidationError(msg)
        await super().save(
            using_db=using_db,
            update_fields=update_fields,
            force_create=force_create,
            force_update=force_update,
        )
