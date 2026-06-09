"""Tests for AvatarService."""

import io
from typing import Any

import pytest
from PIL import Image

from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.user import User
from vapi.domain.services.avatar_svc import AvatarService

pytestmark = pytest.mark.anyio


def _png_bytes() -> bytes:
    """Build a small PNG for upload tests."""
    buf = io.BytesIO()
    Image.new("RGB", (600, 400), color=(10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


async def test_set_avatar_uploads_and_sets_columns(
    company_factory: Any,
    user_factory: Any,
) -> None:
    """Verify setting an avatar creates an image asset and sets the user columns."""
    # Given a user in a company (boto3 is mocked autouse)
    company = await company_factory()
    user = await user_factory(company=company)

    # When setting the avatar
    updated = await AvatarService().set_avatar(
        user=user,
        company_id=company.id,
        acting_user_id=user.id,
        data=_png_bytes(),
    )

    # Then the user records the new image/webp asset's id and url
    assert updated.avatar_asset_id is not None
    asset = await S3Asset.filter(id=updated.avatar_asset_id).first()
    assert asset is not None
    assert asset.mime_type == "image/webp"
    assert str(asset.user_parent_id) == str(user.id)
    assert asset.is_archived is False
    assert updated.avatar_url == asset.public_url


async def test_set_avatar_archives_previous(
    company_factory: Any,
    user_factory: Any,
) -> None:
    """Verify replacing an avatar soft-archives the previous asset."""
    # Given a user who already has an avatar
    company = await company_factory()
    user = await user_factory(company=company)
    svc = AvatarService()
    await svc.set_avatar(
        user=user, company_id=company.id, acting_user_id=user.id, data=_png_bytes()
    )
    user = await User.filter(id=user.id).first()
    first_asset_id = user.avatar_asset_id

    # When setting a new avatar
    updated = await svc.set_avatar(
        user=user, company_id=company.id, acting_user_id=user.id, data=_png_bytes()
    )

    # Then the previous asset is archived with an archive_date and the id moved
    assert updated.avatar_asset_id != first_asset_id
    old = await S3Asset.filter(id=first_asset_id).first()
    assert old.is_archived is True
    assert old.archive_date is not None


async def test_remove_avatar_archives_and_clears_columns(
    company_factory: Any,
    user_factory: Any,
) -> None:
    """Verify removing an avatar archives the asset and nulls the columns."""
    # Given a user with an avatar
    company = await company_factory()
    user = await user_factory(company=company)
    svc = AvatarService()
    await svc.set_avatar(
        user=user, company_id=company.id, acting_user_id=user.id, data=_png_bytes()
    )
    user = await User.filter(id=user.id).first()
    asset_id = user.avatar_asset_id

    # When removing the avatar
    updated = await svc.remove_avatar(user=user)

    # Then both columns are cleared and the asset archived
    assert updated.avatar_asset_id is None
    assert updated.avatar_url is None
    old = await S3Asset.filter(id=asset_id).first()
    assert old.is_archived is True
