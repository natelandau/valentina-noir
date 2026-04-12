"""Integration tests for global admin audit log endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import HTTP_200_OK

from vapi.db.sql_models.audit_log import AuditLog
from vapi.domain.urls import GlobalAdmin

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.developer import Developer

pytestmark = pytest.mark.anyio


async def test_list_developer_audit_logs(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_global_admin: Developer,
    session_company: Company,
) -> None:
    """Verify global admin can list audit logs for a specific developer."""
    # Given an audit log entry exists for the global admin developer
    await AuditLog.create(
        method="POST",
        url="/api/v1/test",
        developer=session_global_admin,
        company=session_company,
        entity_type="COMPANY",
        operation="CREATE",
        description="create company",
    )

    # When the global admin lists audit logs for the developer
    response = await client.get(
        build_url(GlobalAdmin.DEVELOPER_AUDIT_LOGS, developer_id=session_global_admin.id),
        headers=token_global_admin,
    )

    # Then the response is successful with paginated items
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1

    # And each item has structured fields
    item = data["items"][0]
    assert "id" in item
    assert "entity_type" in item
    assert "operation" in item
    assert "description" in item


async def test_list_developer_audit_logs_with_company_filter(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_global_admin: Developer,
    session_company: Company,
) -> None:
    """Verify company_id filter narrows results to a specific company."""
    # Given an audit log entry exists for the developer and company
    await AuditLog.create(
        method="POST",
        url="/api/v1/test",
        developer=session_global_admin,
        company=session_company,
        entity_type="USER",
        operation="CREATE",
        description="create user",
    )

    # When filtering by company_id
    response = await client.get(
        build_url(GlobalAdmin.DEVELOPER_AUDIT_LOGS, developer_id=session_global_admin.id),
        headers=token_global_admin,
        params={"company_id": str(session_company.id)},
    )

    # Then only entries for that company are returned
    assert response.status_code == HTTP_200_OK
    items = response.json()["items"]
    assert all(i["company_id"] == str(session_company.id) for i in items)


async def test_list_developer_audit_logs_with_include(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_global_admin: Developer,
    session_company: Company,
) -> None:
    """Verify include=request_details returns raw request forensics."""
    # Given an audit log entry exists
    await AuditLog.create(
        method="PATCH",
        url="/api/v1/test",
        developer=session_global_admin,
        company=session_company,
    )

    # When including request details
    response = await client.get(
        build_url(GlobalAdmin.DEVELOPER_AUDIT_LOGS, developer_id=session_global_admin.id),
        headers=token_global_admin,
        params={"include": ["request_details"]},
    )

    # Then raw request fields are present
    assert response.status_code == HTTP_200_OK
    item = response.json()["items"][0]
    assert "method" in item
    assert "url" in item
    assert "request_json" in item
