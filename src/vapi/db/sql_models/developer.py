"""Developer and developer company permission models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields

from vapi.constants import CompanyPermission
from vapi.db.sql_models.base import BaseModel

if TYPE_CHECKING:
    from vapi.db.sql_models.audit_log import AuditLog
    from vapi.db.sql_models.company import Company


class Developer(BaseModel):
    """An API developer with key-based authentication."""

    username = fields.CharField(max_length=50, unique=True)
    email = fields.CharField(max_length=255, unique=True)
    is_global_admin = fields.BooleanField(default=False)
    api_key_fingerprint = fields.CharField(max_length=255, null=True, db_index=True)
    hashed_api_key = fields.CharField(max_length=255, null=True)
    key_generated = fields.DatetimeField(null=True)

    # Reverse relations
    permissions: fields.ReverseRelation[DeveloperCompanyPermission]
    audit_logs: fields.ReverseRelation[AuditLog]

    class Meta:
        """Tortoise ORM meta options."""

        table = "developer"


class DeveloperCompanyPermission(BaseModel):
    """Permission linking a developer to a company with a specific role."""

    developer: fields.ForeignKeyRelation[Developer] = fields.ForeignKeyField(
        "models.Developer", related_name="permissions", on_delete=fields.OnDelete.CASCADE
    )
    company: fields.ForeignKeyRelation[Company] = fields.ForeignKeyField(
        "models.Company",
        related_name="developer_permissions",
        on_delete=fields.OnDelete.CASCADE,
    )
    permission = fields.CharEnumField(CompanyPermission)

    class Meta:
        """Tortoise ORM meta options."""

        table = "developer_company_permission"
        unique_together = (("developer", "company"),)
