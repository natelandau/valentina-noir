"""Test that changes to a developer's key or privileges take effect despite the auth cache."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
)

from vapi.constants import AUTH_HEADER_KEY, IGNORE_RATE_LIMIT_HEADER_KEY
from vapi.domain.services.developer_svc import DeveloperService
from vapi.domain.urls import Developers, GlobalAdmin

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

pytestmark = pytest.mark.anyio

_developer_service = DeveloperService()


async def _developer_token(
    developer_factory: Callable[..., Any], **kwargs: Any
) -> tuple[Any, dict[str, str]]:
    developer = await developer_factory(**kwargs)
    api_key = await _developer_service.generate_api_key(developer)
    return developer, {AUTH_HEADER_KEY: api_key, IGNORE_RATE_LIMIT_HEADER_KEY: "true"}


async def test_rotated_key_is_rejected(
    client: AsyncClient,
    build_url: Callable[..., str],
    developer_factory: Callable[..., Any],
) -> None:
    """Verify an old API key stops working after the developer rotates it."""
    # Given a developer whose key is already in the auth cache
    _, old_token = await _developer_token(developer_factory)
    assert (
        await client.get(build_url(Developers.ME), headers=old_token)
    ).status_code == HTTP_200_OK

    # When the developer rotates their key
    response = await client.post(build_url(Developers.NEW_KEY), headers=old_token)
    assert response.status_code == HTTP_201_CREATED

    # Then the old key is rejected
    response = await client.get(build_url(GlobalAdmin.DEVELOPERS), headers=old_token)
    assert response.status_code == HTTP_401_UNAUTHORIZED


async def test_admin_rotated_key_is_rejected(
    client: AsyncClient,
    build_url: Callable[..., str],
    developer_factory: Callable[..., Any],
    token_global_admin: dict[str, str],
) -> None:
    """Verify a developer's old key stops working after a global admin rotates it."""
    # Given a developer whose key is already in the auth cache
    target, target_token = await _developer_token(developer_factory)
    assert (
        await client.get(build_url(Developers.ME), headers=target_token)
    ).status_code == HTTP_200_OK

    # When a global admin issues the developer a new key
    response = await client.post(
        build_url(GlobalAdmin.DEVELOPER_NEW_KEY, developer_id=target.id), headers=token_global_admin
    )
    assert response.status_code == HTTP_201_CREATED

    # Then the old key is rejected
    response = await client.get(build_url(Developers.ME), headers=target_token)
    assert response.status_code == HTTP_401_UNAUTHORIZED


async def test_demoted_global_admin_loses_admin_access(
    client: AsyncClient,
    build_url: Callable[..., str],
    developer_factory: Callable[..., Any],
    token_global_admin: dict[str, str],
) -> None:
    """Verify a demoted global admin loses admin access immediately."""
    # Given a global admin whose privileges are already in the auth cache
    target, target_token = await _developer_token(developer_factory, is_global_admin=True)
    assert (
        await client.get(build_url(GlobalAdmin.DEVELOPERS), headers=target_token)
    ).status_code == HTTP_200_OK

    # When another global admin demotes them
    response = await client.patch(
        build_url(GlobalAdmin.DEVELOPER_UPDATE, developer_id=target.id),
        headers=token_global_admin,
        json={"is_global_admin": False},
    )
    assert response.status_code == HTTP_200_OK

    # Then admin routes reject the demoted developer
    response = await client.get(build_url(GlobalAdmin.DEVELOPERS), headers=target_token)
    assert response.status_code == HTTP_403_FORBIDDEN


async def test_archived_developer_is_rejected(
    client: AsyncClient,
    build_url: Callable[..., str],
    developer_factory: Callable[..., Any],
    token_global_admin: dict[str, str],
) -> None:
    """Verify an archived developer's key stops working immediately."""
    # Given a global admin whose key is already in the auth cache
    target, target_token = await _developer_token(developer_factory, is_global_admin=True)
    assert (
        await client.get(build_url(GlobalAdmin.DEVELOPERS), headers=target_token)
    ).status_code == HTTP_200_OK

    # When another global admin archives them
    response = await client.delete(
        build_url(GlobalAdmin.DEVELOPER_DELETE, developer_id=target.id), headers=token_global_admin
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    # Then the archived developer's key is rejected
    response = await client.get(build_url(GlobalAdmin.DEVELOPERS), headers=target_token)
    assert response.status_code == HTTP_401_UNAUTHORIZED
