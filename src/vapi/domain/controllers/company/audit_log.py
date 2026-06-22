"""Company-scoped audit log controller."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get
from litestar.params import Parameter

from vapi.constants import AuditEntityType, AuditOperation
from vapi.db.sql_models.company import Company
from vapi.domain import deps, urls
from vapi.domain.audit import (
    AuditLogDetailResponse,
    AuditLogInclude,
    AuditLogResponse,
    build_audit_log_filters,
    list_audit_logs,
)
from vapi.domain.paginator import OffsetPagination
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import docs


class CompanyAuditLogController(Controller):
    """Company-scoped audit log controller."""

    tags = [APITags.COMPANIES.name]
    guards = [developer_company_user_guard]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "requesting_developer": Provide(deps.provide_developer_from_request),
    }

    @get(
        path=urls.Companies.AUDIT_LOGS,
        summary="List company audit logs",
        operation_id="listCompanyAuditLogs",
        description=docs.LIST_AUDIT_LOGS_DESCRIPTION,
        cache=True,
    )
    async def list_company_audit_logs(  # noqa: PLR0913
        self,
        *,
        company: Company,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
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
        """List audit log entries for a company."""
        filters = build_audit_log_filters(
            base={"company_id": company.id},
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
