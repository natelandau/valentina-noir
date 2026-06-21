"""Global admin audit log controller."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get
from litestar.params import Parameter

from vapi.constants import AuditEntityType, AuditOperation
from vapi.db.sql_models.developer import Developer
from vapi.domain import deps, urls
from vapi.domain.audit import (
    AuditLogDetailResponse,
    AuditLogInclude,
    AuditLogResponse,
    build_audit_log_filters,
    list_audit_logs,
)
from vapi.domain.paginator import OffsetPagination
from vapi.lib.guards import global_admin_guard
from vapi.openapi.tags import APITags

from . import docs


class GlobalAdminAuditLogController(Controller):
    """Global admin audit log controller for monitoring developer activity."""

    tags = [APITags.GLOBAL_ADMIN.name]
    guards = [global_admin_guard]
    dependencies = {
        "developer": Provide(deps.provide_developer_by_id),
    }

    @get(
        path=urls.GlobalAdmin.DEVELOPER_AUDIT_LOGS,
        summary="List developer audit logs",
        operation_id="globalAdminListDeveloperAuditLogs",
        description=docs.LIST_DEVELOPER_AUDIT_LOGS_DESCRIPTION,
        cache=True,
    )
    async def list_developer_audit_logs(  # noqa: PLR0913
        self,
        *,
        developer: Developer,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        company_id: UUID | None = None,
        acting_user_id: UUID | None = None,
        user_id: UUID | None = None,
        campaign_id: UUID | None = None,
        book_id: UUID | None = None,
        chapter_id: UUID | None = None,
        character_id: UUID | None = None,
        entity_type: AuditEntityType | None = None,
        operation: AuditOperation | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        include: list[AuditLogInclude] | None = None,
    ) -> OffsetPagination[AuditLogResponse] | OffsetPagination[AuditLogDetailResponse]:
        """List audit log entries for a developer."""
        filters = build_audit_log_filters(
            base={"developer_id": developer.id},
            company_id=company_id,
            acting_user_id=acting_user_id,
            user_id=user_id,
            campaign_id=campaign_id,
            book_id=book_id,
            chapter_id=chapter_id,
            character_id=character_id,
            entity_type=entity_type,
            operation=operation,
        )

        return await list_audit_logs(
            filters=filters,
            limit=limit,
            offset=offset,
            date_from=date_from,
            date_to=date_to,
            include_request_details=bool(include and AuditLogInclude.REQUEST_DETAILS in include),
        )
