"""Audit log query service - shared by company and global admin controllers."""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

from vapi.constants import AuditEntityType, AuditOperation
from vapi.db.sql_models.audit_log import AuditLog
from vapi.domain.paginator import OffsetPagination

from .dto import AuditLogDetailResponse, AuditLogResponse


def build_audit_log_filters(  # noqa: PLR0913
    *,
    base: dict[str, object],
    company_id: UUID | None = None,
    acting_user_id: UUID | None = None,
    user_id: UUID | None = None,
    campaign_id: UUID | None = None,
    book_id: UUID | None = None,
    chapter_id: UUID | None = None,
    character_id: UUID | None = None,
    entity_type: AuditEntityType | None = None,
    operation: AuditOperation | None = None,
) -> dict[str, object]:
    """Build an audit-log filter dict from a base scope plus optional column filters.

    The company and global-admin controllers differ only in their base scope
    (`company_id` vs `developer_id`); every other filter is applied identically
    here so the two controllers stay in lock-step.

    Args:
        base: The mandatory scope filter (e.g. {"company_id": ...} or {"developer_id": ...}).
        company_id: Optional company filter (global-admin only).
        acting_user_id: Optional acting-user filter.
        user_id: Optional subject-user filter.
        campaign_id: Optional campaign filter.
        book_id: Optional book filter.
        chapter_id: Optional chapter filter.
        character_id: Optional character filter.
        entity_type: Optional entity-type filter.
        operation: Optional operation filter.

    Returns:
        A filter dict suitable for passing to list_audit_logs.
    """
    optional: dict[str, object | None] = {
        "company_id": company_id,
        "acting_user_id": acting_user_id,
        "user_id": user_id,
        "campaign_id": campaign_id,
        "book_id": book_id,
        "chapter_id": chapter_id,
        "character_id": character_id,
        "entity_type": entity_type,
        "operation": operation,
    }
    return {**base, **{key: value for key, value in optional.items() if value is not None}}


async def list_audit_logs(
    *,
    filters: dict[str, Any],
    limit: int,
    offset: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_request_details: bool = False,
) -> OffsetPagination[AuditLogResponse] | OffsetPagination[AuditLogDetailResponse]:
    """Query audit logs with filters, pagination, and optional request details.

    Build a Tortoise QuerySet from the provided filters and date range, then
    return a paginated result set sorted by date_created descending.

    Args:
        filters: Dict of field=value pairs passed directly to QuerySet.filter().
        limit: Maximum number of results to return.
        offset: Number of results to skip.
        date_from: If provided, only include entries on or after this timestamp.
        date_to: If provided, only include entries on or before this timestamp.
        include_request_details: When True, return AuditLogDetailResponse with
            raw request forensics instead of the default AuditLogResponse.

    Returns:
        OffsetPagination wrapping the appropriate response DTO type.
    """
    qs = AuditLog.filter(**filters)

    if date_from is not None:
        qs = qs.filter(date_created__gte=date_from)
    if date_to is not None:
        qs = qs.filter(date_created__lte=date_to)

    count, entries = await asyncio.gather(
        qs.count(),
        qs.order_by("-date_created").offset(offset).limit(limit),
    )

    if include_request_details:
        return OffsetPagination(
            items=[AuditLogDetailResponse.from_model(e) for e in entries],
            limit=limit,
            offset=offset,
            total=count,
        )

    return OffsetPagination(
        items=[AuditLogResponse.from_model(e) for e in entries],
        limit=limit,
        offset=offset,
        total=count,
    )
