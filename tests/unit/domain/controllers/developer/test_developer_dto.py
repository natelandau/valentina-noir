"""Unit tests for developer response DTOs."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import msgspec
import pytest

from vapi.constants import CompanyPermission
from vapi.db.sql_models.developer import Developer
from vapi.domain.controllers.developer.dto import DeveloperApiKeyResponse, DeveloperResponse
from vapi.domain.controllers.global_admin.dto import (
    DeveloperAdminApiKeyResponse,
    DeveloperAdminResponse,
)

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


async def test_admin_api_key_response_encodes_like_admin_response(
    developer_factory: Callable[..., Any],
) -> None:
    """Verify the admin API key response is the admin developer response plus api_key."""
    # Given a developer with permissions loaded
    developer = await developer_factory()
    loaded = (
        await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()
    )

    # When encoding both responses
    with_key = msgspec.json.decode(
        msgspec.json.encode(
            DeveloperAdminApiKeyResponse.from_model_with_key(loaded, api_key="new-key")
        )
    )
    base = msgspec.json.decode(msgspec.json.encode(DeveloperAdminResponse.from_model(loaded)))

    # Then they differ only by api_key
    assert with_key.pop("api_key") == "new-key"
    assert with_key == base


async def test_api_key_response_encoding(
    developer_factory: Callable[..., Any],
) -> None:
    """Verify the self-service API key response encodes its fields and a whole-second UTC timestamp."""
    # Given a developer whose key was generated at a whole second
    developer = await developer_factory()
    developer.key_generated = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

    # When encoding the response
    encoded = msgspec.json.encode(DeveloperApiKeyResponse.from_model(developer, api_key="new-key"))

    # Then the bytes match the expected JSON
    assert encoded == msgspec.json.encode(
        {
            "id": str(developer.id),
            "username": developer.username,
            "email": developer.email,
            "api_key": "new-key",
            "key_generated": "2026-01-02T03:04:05Z",
        }
    )


async def test_api_key_response_requires_key_generated(
    developer_factory: Callable[..., Any],
) -> None:
    """Verify the self-service API key response refuses a developer with no key timestamp."""
    # Given a developer with no key_generated timestamp
    developer = await developer_factory()
    developer.key_generated = None

    # When / Then building the response raises
    with pytest.raises(ValueError, match="key_generated"):
        DeveloperApiKeyResponse.from_model(developer, api_key="new-key")
