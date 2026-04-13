"""Audit log model — API request tracking with structured query fields."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tortoise import fields

from vapi.constants import AuditEntityType, AuditOperation
from vapi.db.sql_models.base import BaseModel

if TYPE_CHECKING:
    from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
    from vapi.db.sql_models.character import Character
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.developer import Developer
    from vapi.db.sql_models.user import User


class AuditLog(BaseModel):
    """An audit trail entry for API requests.

    Combines raw request forensics (method, url, request_json, etc.) with structured
    query fields (entity_type, operation, FK columns) for efficient filtering.
    """

    summary = fields.TextField(null=True)
    operation_id = fields.CharField(max_length=255, null=True)
    handler_name = fields.CharField(max_length=255, null=True)
    handler = fields.CharField(max_length=255, null=True)
    method = fields.CharField(max_length=10)
    url = fields.TextField()
    request_json: Any = fields.JSONField(null=True)
    request_body = fields.TextField(null=True)
    path_params: Any = fields.JSONField(null=True)
    query_params: Any = fields.JSONField(null=True)
    request_id = fields.CharField(max_length=255, null=True)

    developer: fields.ForeignKeyRelation[Developer] = fields.ForeignKeyField(
        "models.Developer", related_name="audit_logs", on_delete=fields.OnDelete.CASCADE
    )

    entity_type = fields.CharEnumField(AuditEntityType, null=True)
    operation = fields.CharEnumField(AuditOperation, null=True)
    target_entity_id = fields.UUIDField(null=True)
    description = fields.TextField(null=True)
    changes: Any = fields.JSONField(null=True)

    company: fields.ForeignKeyNullableRelation[Company] = fields.ForeignKeyField(
        "models.Company",
        related_name="audit_logs",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )
    acting_user: fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="audit_logs_acted",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )
    user: fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="audit_logs_targeted",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )
    campaign: fields.ForeignKeyNullableRelation[Campaign] = fields.ForeignKeyField(
        "models.Campaign",
        related_name="audit_logs",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )
    book: fields.ForeignKeyNullableRelation[CampaignBook] = fields.ForeignKeyField(
        "models.CampaignBook",
        related_name="audit_logs",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )
    chapter: fields.ForeignKeyNullableRelation[CampaignChapter] = fields.ForeignKeyField(
        "models.CampaignChapter",
        related_name="audit_logs",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )
    character: fields.ForeignKeyNullableRelation[Character] = fields.ForeignKeyField(
        "models.Character",
        related_name="audit_logs",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )

    class Meta:
        """Tortoise ORM meta options."""

        table = "audit_log"
        indexes = [  # noqa: RUF012
            ("company_id", "entity_type"),
            ("company_id", "date_created"),
            ("developer_id", "date_created"),
        ]
