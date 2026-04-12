"""Audit log query service — shared by company and global admin controllers."""

import asyncio
from datetime import datetime
from typing import Any

from vapi.db.sql_models.audit_log import AuditLog
from vapi.domain.paginator import OffsetPagination

from .audit_log_dto import AuditLogDetailResponse, AuditLogResponse


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
