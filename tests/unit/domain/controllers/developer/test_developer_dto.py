"""Unit tests for developer response DTOs."""

from collections.abc import Callable
from typing import Any

import pytest

from vapi.constants import CompanyPermission
from vapi.db.sql_models.developer import Developer
from vapi.domain.controllers.developer.dto import DeveloperResponse
from vapi.domain.controllers.global_admin.dto import DeveloperAdminResponse

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("response_cls", [DeveloperResponse, DeveloperAdminResponse])
async def test_revoked_companies_are_not_listed(
    response_cls: Any,
    company_factory: Callable[..., Any],
    developer_factory: Callable[..., Any],
    developer_company_permission_factory: Callable[..., Any],
) -> None:
    """Verify a REVOKE permission row does not list the company as one the developer can use."""
    # Given a developer with USER on one company and a REVOKE row on another
    developer = await developer_factory()
    kept = await company_factory()
    revoked = await company_factory()
    await developer_company_permission_factory(
        developer=developer, company=kept, permission=CompanyPermission.USER
    )
    await developer_company_permission_factory(
        developer=developer, company=revoked, permission=CompanyPermission.REVOKE
    )
    loaded = (
        await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()
    )

    # When building the response
    response = response_cls.from_model(loaded)

    # Then only the USER company is listed
    assert [c.company_id for c in response.companies] == [kept.id]
