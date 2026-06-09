"""Test user avatar endpoints."""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import HTTP_200_OK, HTTP_403_FORBIDDEN
from PIL import Image

from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.user import User
from vapi.domain.handlers.archive_handlers import archive_user
from vapi.domain.urls import Users

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.developer import Developer

pytestmark = pytest.mark.anyio


def _png() -> tuple[str, bytes]:
    """Build a non-square PNG upload payload."""
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), color=(40, 80, 120)).save(buf, format="PNG")
    return ("face.png", buf.getvalue())


async def test_set_avatar_returns_avatar_url(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_company_admin: Developer,
    user_factory: Callable,
) -> None:
    """Verify uploading an avatar stores a webp asset and returns avatar_url."""
    # Given a user uploading their own avatar
    user = await user_factory(company=session_company, role="PLAYER")
    filename, data = _png()

    # When PUTting the avatar
    response = await client.put(
        build_url(Users.AVATAR, company_id=session_company.id, user_id=user.id),
        headers=token_company_admin | {"On-Behalf-Of": str(user.id)},
        files={"upload": (filename, data, "image/png")},
    )

    # Then the response carries a cloudfront avatar_url and a webp asset exists
    assert response.status_code == HTTP_200_OK
    body = response.json()
    assert body["avatar_url"] is not None
    assert re.match(
        rf"^MOCK_URL/{session_company.id}/{user.id}/image/.+\.webp$", body["avatar_url"]
    )
    refreshed = await User.filter(id=user.id).first()
    asset = await S3Asset.filter(id=refreshed.avatar_asset_id).first()
    assert asset.mime_type == "image/webp"


async def test_replace_avatar_archives_previous(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_company_admin: Developer,
    user_factory: Callable,
) -> None:
    """Verify replacing an avatar archives the previous asset."""
    # Given a user with an existing avatar
    user = await user_factory(company=session_company, role="PLAYER")
    url = build_url(Users.AVATAR, company_id=session_company.id, user_id=user.id)
    headers = token_company_admin | {"On-Behalf-Of": str(user.id)}
    filename, data = _png()
    await client.put(url, headers=headers, files={"upload": (filename, data, "image/png")})
    first = await User.filter(id=user.id).first()
    first_asset_id = first.avatar_asset_id

    # When uploading a replacement
    _, replacement = _png()
    await client.put(
        url, headers=headers, files={"upload": ("face2.png", replacement, "image/png")}
    )

    # Then the previous asset is archived
    old = await S3Asset.filter(id=first_asset_id).first()
    assert old.is_archived is True
    assert old.archive_date is not None


async def test_delete_avatar_clears_url(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_company_admin: Developer,
    user_factory: Callable,
) -> None:
    """Verify deleting an avatar archives the asset and returns null avatar_url."""
    # Given a user with an avatar
    user = await user_factory(company=session_company, role="PLAYER")
    url = build_url(Users.AVATAR, company_id=session_company.id, user_id=user.id)
    headers = token_company_admin | {"On-Behalf-Of": str(user.id)}
    filename, data = _png()
    await client.put(url, headers=headers, files={"upload": (filename, data, "image/png")})

    # When deleting the avatar
    response = await client.delete(url, headers=headers)

    # Then avatar_url is null
    assert response.status_code == HTTP_200_OK
    assert response.json()["avatar_url"] is None


async def test_set_avatar_forbidden_for_other_non_admin(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_company_admin: Developer,
    session_user: User,
    user_factory: Callable,
) -> None:
    """Verify a non-admin user cannot set another user's avatar."""
    # Given a second, non-admin user acting on the first user's avatar
    other = await user_factory(company=session_company, role="PLAYER")
    filename, data = _png()

    # When the other user PUTs the target user's avatar
    response = await client.put(
        build_url(Users.AVATAR, company_id=session_company.id, user_id=session_user.id),
        headers=token_company_admin | {"On-Behalf-Of": str(other.id)},
        files={"upload": (filename, data, "image/png")},
    )

    # Then the request is forbidden
    assert response.status_code == HTTP_403_FORBIDDEN


async def test_archiving_user_archives_avatar(
    user_factory: Callable,
    company_factory: Callable,
    s3asset_factory: Callable,
) -> None:
    """Verify archiving a user cascades to their avatar asset."""
    # Given a user whose avatar asset is owned via user_parent
    company = await company_factory()
    user = await user_factory(company=company)
    asset = await s3asset_factory(company=company, user_parent=user)
    user.avatar_url = asset.public_url
    user.avatar_asset_id = asset.id
    await user.save()

    # When archiving the user
    await archive_user(user)

    # Then the avatar asset is archived too
    refreshed = await S3Asset.filter(id=asset.id).first()
    assert refreshed.is_archived is True
    assert refreshed.archive_date is not None


async def test_delete_avatar_when_none_exists(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_company_admin: Developer,
    user_factory: Callable,
) -> None:
    """Verify deleting a non-existent avatar is a no-op returning null avatar_url."""
    # Given a user with no custom avatar
    user = await user_factory(company=session_company, role="PLAYER")
    url = build_url(Users.AVATAR, company_id=session_company.id, user_id=user.id)
    headers = token_company_admin | {"On-Behalf-Of": str(user.id)}

    # When deleting the (absent) avatar
    response = await client.delete(url, headers=headers)

    # Then the request succeeds and avatar_url is null
    assert response.status_code == HTTP_200_OK
    assert response.json()["avatar_url"] is None
