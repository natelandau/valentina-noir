"""Audit log response DTOs and include enum."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

import msgspec

from vapi.db.sql_models.audit_log import AuditLog


class AuditLogInclude(StrEnum):
    """Child data that can be embedded in an audit log response."""

    REQUEST_DETAILS = "request_details"


def _base_fields(m: AuditLog) -> dict[str, Any]:
    """Extract the shared structured fields from an AuditLog instance."""
    return {
        "id": m.id,
        "date_created": m.date_created,
        "entity_type": m.entity_type.value if m.entity_type else None,
        "operation": m.operation.value if m.operation else None,
        "target_entity_id": m.target_entity_id,
        "description": m.description,
        "changes": m.changes,
        "company_id": m.company_id,  # type: ignore[attr-defined]
        "acting_user_id": m.acting_user_id,  # type: ignore[attr-defined]
        "user_id": m.user_id,  # type: ignore[attr-defined]
        "campaign_id": m.campaign_id,  # type: ignore[attr-defined]
        "book_id": m.book_id,  # type: ignore[attr-defined]
        "chapter_id": m.chapter_id,  # type: ignore[attr-defined]
        "character_id": m.character_id,  # type: ignore[attr-defined]
        "request_id": m.request_id,
        "summary": m.summary,
    }


class AuditLogResponse(msgspec.Struct):
    """End-user focused audit log entry — structured fields only."""

    id: UUID
    date_created: datetime
    entity_type: str | None
    operation: str | None
    target_entity_id: UUID | None
    description: str | None
    changes: dict | None
    company_id: UUID | None
    acting_user_id: UUID | None
    user_id: UUID | None
    campaign_id: UUID | None
    book_id: UUID | None
    chapter_id: UUID | None
    character_id: UUID | None
    request_id: str | None
    summary: str | None

    @classmethod
    def from_model(cls, m: AuditLog) -> "AuditLogResponse":
        """Convert a Tortoise AuditLog to a response Struct."""
        return cls(**_base_fields(m))


class AuditLogDetailResponse(msgspec.Struct):
    """Internal/forensics focused audit log entry — includes raw request data."""

    id: UUID
    date_created: datetime
    entity_type: str | None
    operation: str | None
    target_entity_id: UUID | None
    description: str | None
    changes: dict | None
    company_id: UUID | None
    acting_user_id: UUID | None
    user_id: UUID | None
    campaign_id: UUID | None
    book_id: UUID | None
    chapter_id: UUID | None
    character_id: UUID | None
    request_id: str | None
    summary: str | None
    method: str
    url: str
    request_json: dict | None
    request_body: str | None
    path_params: dict | None
    query_params: dict | None
    operation_id: str | None
    handler_name: str | None

    @classmethod
    def from_model(cls, m: AuditLog) -> "AuditLogDetailResponse":
        """Convert a Tortoise AuditLog to a detail response Struct."""
        return cls(
            **_base_fields(m),
            method=m.method,
            url=m.url,
            request_json=m.request_json,
            request_body=m.request_body,
            path_params=m.path_params,
            query_params=m.query_params,
            operation_id=m.operation_id,
            handler_name=m.handler_name,
        )
