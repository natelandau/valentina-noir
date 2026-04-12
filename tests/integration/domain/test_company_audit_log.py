"""Integration tests for company-scoped audit log endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import HTTP_200_OK

from vapi.db.sql_models.audit_log import AuditLog
from vapi.domain.urls import Companies

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.developer import Developer

pytestmark = pytest.mark.anyio


async def test_list_company_audit_logs(
    client: AsyncClient,
    token_company_owner: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_company_owner: Developer,
) -> None:
    """Verify listing audit logs returns paginated results scoped to the company."""
    # Given an audit log entry exists for the company
    await AuditLog.create(
        method="POST",
        url="/api/v1/test",
        developer=session_company_owner,
        company=session_company,
        entity_type="CAMPAIGN",
        operation="CREATE",
        description="create campaign",
    )

    # When listing audit logs for the company
    response = await client.get(
        build_url(Companies.AUDIT_LOGS, company_id=session_company.id),
        headers=token_company_owner,
    )

    # Then the response is successful with paginated items
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert len(data["items"]) >= 1

    # And each item has the expected structured fields
    item = data["items"][0]
    assert "id" in item
    assert "date_created" in item
    assert "entity_type" in item
    assert "operation" in item
    assert "description" in item
    assert "company_id" in item
    assert "request_id" in item

    # And raw request fields are NOT present by default
    assert "url" not in item
    assert "request_json" not in item
    assert "method" not in item


async def test_list_company_audit_logs_with_include(
    client: AsyncClient,
    token_company_owner: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_company_owner: Developer,
) -> None:
    """Verify include=request_details returns raw request forensics."""
    # Given an audit log entry exists for the company
    await AuditLog.create(
        method="PATCH",
        url="/api/v1/test",
        developer=session_company_owner,
        company=session_company,
        entity_type="USER",
        operation="UPDATE",
        description="update user",
    )

    # When listing audit logs with include=request_details
    response = await client.get(
        build_url(Companies.AUDIT_LOGS, company_id=session_company.id),
        headers=token_company_owner,
        params={"include": ["request_details"]},
    )

    # Then the response includes raw request fields
    assert response.status_code == HTTP_200_OK
    item = response.json()["items"][0]
    assert "method" in item
    assert "url" in item
    assert "request_json" in item
    assert "request_body" in item
    assert "path_params" in item
    assert "query_params" in item


async def test_list_company_audit_logs_with_filters(
    client: AsyncClient,
    token_company_owner: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_company_owner: Developer,
) -> None:
    """Verify entity_type and operation filters narrow results."""
    # Given audit log entries of different types exist
    await AuditLog.create(
        method="POST",
        url="/api/v1/test",
        developer=session_company_owner,
        company=session_company,
        entity_type="CHARACTER",
        operation="CREATE",
        description="create character",
    )
    await AuditLog.create(
        method="DELETE",
        url="/api/v1/test",
        developer=session_company_owner,
        company=session_company,
        entity_type="CAMPAIGN",
        operation="DELETE",
        description="delete campaign",
    )

    # When filtering by entity_type=CHARACTER and operation=CREATE
    response = await client.get(
        build_url(Companies.AUDIT_LOGS, company_id=session_company.id),
        headers=token_company_owner,
        params={"entity_type": "CHARACTER", "operation": "CREATE"},
    )

    # Then only matching entries are returned
    assert response.status_code == HTTP_200_OK
    items = response.json()["items"]
    assert all(i["entity_type"] == "CHARACTER" for i in items)
    assert all(i["operation"] == "CREATE" for i in items)


async def test_list_company_audit_logs_pagination(
    client: AsyncClient,
    token_company_owner: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_company_owner: Developer,
) -> None:
    """Verify limit and offset parameters control pagination."""
    # Given multiple audit log entries exist
    for i in range(3):
        await AuditLog.create(
            method="POST",
            url=f"/api/v1/test/{i}",
            developer=session_company_owner,
            company=session_company,
        )

    # When requesting with limit=1 and offset=0
    response = await client.get(
        build_url(Companies.AUDIT_LOGS, company_id=session_company.id),
        headers=token_company_owner,
        params={"limit": 1, "offset": 0},
    )

    # Then only one item is returned but total reflects all entries
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert len(data["items"]) == 1
    assert data["limit"] == 1
    assert data["offset"] == 0
    assert data["total"] >= 3
