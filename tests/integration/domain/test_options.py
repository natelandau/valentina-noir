"""Test options."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar.status_codes import HTTP_200_OK

from vapi.config import settings
from vapi.constants import (
    DiceSize,
    PermissionManageCampaign,
    PermissionsFreeTraitChanges,
    PermissionsGrantXP,
    RollResultType,
    UserRole,
)
from vapi.domain import urls

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient


async def test_get_company_options(
    client: AsyncClient,
    build_url: Callable[[str, Any], str],
    token_company_user: dict[str, str],
    debug: Callable[[Any], None],
) -> None:
    """Verify the routes are working for a company user."""
    response = await client.get(build_url(urls.Options.LIST), headers=token_company_user)

    assert response.status_code == HTTP_200_OK
    assert response.json()["companies"] == {
        "PermissionManageCampaign": [x.name for x in PermissionManageCampaign],
        "PermissionsGrantXP": [x.name for x in PermissionsGrantXP],
        "PermissionsFreeTraitChanges": [x.name for x in PermissionsFreeTraitChanges],
    }
    assert response.json()["users"] == {
        "UserRole": [x.name for x in UserRole],
    }
    assert response.json()["gameplay"] == {
        "DiceSize": [x.name for x in DiceSize],
        "RollResultType": [x.name for x in RollResultType],
    }
    assert "characters" in response.json()
    assert (
        response.json()["characters"]["_related"]["traits"]
        == f"{settings.server.url}{urls.CharacterBlueprints.TRAITS.replace(':str', '')}"
    )
