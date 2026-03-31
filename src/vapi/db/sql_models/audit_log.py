"""Audit log model — API request tracking."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tortoise import fields

from vapi.db.sql_models.base import BaseModel

if TYPE_CHECKING:
    from vapi.db.sql_models.developer import Developer


class AuditLog(BaseModel):
    """An audit trail entry for API requests."""

    developer: fields.ForeignKeyRelation[Developer] = fields.ForeignKeyField(
        "models.Developer", related_name="audit_logs", on_delete=fields.OnDelete.CASCADE
    )
    name = fields.CharField(max_length=255, null=True)
    summary = fields.TextField(null=True)
    description = fields.TextField(null=True)
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

    class Meta:
        """Tortoise ORM meta options."""

        table = "audit_log"
