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
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services.audit_log_dto import (
    AuditLogDetailResponse,
    AuditLogInclude,
    AuditLogResponse,
)
from vapi.domain.services.audit_log_svc import list_audit_logs
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import audit_log_docs as docs


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
        filters: dict[str, object] = {"company_id": company.id}

        if acting_user_id is not None:
            filters["acting_user_id"] = acting_user_id
        if user_id is not None:
            filters["user_id"] = user_id
        if campaign_id is not None:
            filters["campaign_id"] = campaign_id
        if book_id is not None:
            filters["book_id"] = book_id
        if chapter_id is not None:
            filters["chapter_id"] = chapter_id
        if character_id is not None:
            filters["character_id"] = character_id
        if entity_type is not None:
            filters["entity_type"] = entity_type
        if operation is not None:
            filters["operation"] = operation

        return await list_audit_logs(
            filters=filters,
            limit=limit,
            offset=offset,
            date_from=date_from,
            date_to=date_to,
            include_request_details=bool(include and AuditLogInclude.REQUEST_DETAILS in include),
        )
