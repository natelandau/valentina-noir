"""Test S3 asset controllers (Tortoise ORM)."""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)
from PIL import Image

from vapi.constants import AssetType
from vapi.db.sql_models.aws import S3Asset
from vapi.domain.urls import Campaigns, Characters, Users

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.developer import Developer
    from vapi.db.sql_models.user import User

pytestmark = pytest.mark.anyio


def _png_bytes() -> bytes:
    """Build encoded PNG bytes for asset-upload tests."""
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


async def test_list_assets(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_company_admin: Developer,
    session_user: User,
    session_campaign: Campaign,
    character_factory: Callable,
    s3asset_factory: Callable,
    debug: Callable[[...], None],
) -> None:
    """Verify listing assets filtered by type returns correct results."""
    # Given: A character with image assets and a text asset
    character = await character_factory(
        company=session_company,
        user_player=session_user,
        user_creator=session_user,
        campaign=session_campaign,
    )
    image_assets = []
    for _ in range(3):
        asset = await s3asset_factory(
            asset_type=AssetType.IMAGE,
            uploaded_by=session_user,
            character=character,
            company=session_company,
        )
        image_assets.append(asset)

    # And a text asset that should not be returned when filtering by IMAGE
    await s3asset_factory(
        asset_type=AssetType.TEXT,
        uploaded_by=session_user,
        character=character,
        company=session_company,
    )

    # And an unrelated asset (no character FK)
    await s3asset_factory(
        asset_type=AssetType.IMAGE,
        uploaded_by=session_user,
        company=session_company,
    )

    # When: Listing assets filtered by IMAGE type
    response = await client.get(
        build_url(
            Characters.ASSETS,
            company_id=session_company.id,
            character_id=character.id,
        ),
        headers=token_company_admin | {"On-Behalf-Of": str(session_user.id)},
        params={"asset_type": AssetType.IMAGE.value},
    )
    # debug(response.json())

    # Then: Response is successful with 3 image assets
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["items"]) == 3
    assert response_json["limit"] == 10
    assert response_json["offset"] == 0
    assert response_json["total"] == 3


async def test_get_asset(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_company_admin: Developer,
    session_user: User,
    s3asset_factory: Callable,
    debug: Callable[[...], None],
) -> None:
    """Verify getting a single user asset returns correct data."""
    # Given: A user with an asset
    asset = await s3asset_factory(
        asset_type=AssetType.TEXT,
        uploaded_by=session_user,
        user_parent=session_user,
        company=session_company,
    )

    # When: Getting the asset
    response = await client.get(
        build_url(
            Users.ASSET_DETAIL,
            company_id=session_company.id,
            user_id=session_user.id,
            asset_id=asset.id,
        ),
        headers=token_company_admin | {"On-Behalf-Of": str(session_user.id)},
    )
    # debug(response.json())

    # Then: Response is successful
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == str(asset.id)
    assert response_json["asset_type"] == AssetType.TEXT.value
    assert response_json["user_parent_id"] == str(session_user.id)


async def test_get_asset_not_parent(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_company_admin: Developer,
    session_user: User,
    session_campaign: Campaign,
    session_campaign_book: CampaignBook,
    session_campaign_chapter: CampaignChapter,
    s3asset_factory: Callable,
    debug: Callable[[...], None],
) -> None:
    """Verify getting an asset with wrong parent returns 404."""
    # Given: An asset belonging to a different chapter (mismatched FK)
    asset = await s3asset_factory(
        asset_type=AssetType.TEXT,
        chapter=None,
        company=session_company,
        uploaded_by=session_user,
    )

    # When: Getting the asset via the chapter's URL
    response = await client.get(
        build_url(
            Campaigns.CHAPTER_ASSET_DETAIL,
            company_id=session_company.id,
            campaign_id=session_campaign.id,
            book_id=session_campaign_book.id,
            chapter_id=session_campaign_chapter.id,
            asset_id=asset.id,
        ),
        headers=token_company_admin | {"On-Behalf-Of": str(session_user.id)},
    )

    # Then: Response is 404
    assert response.status_code == HTTP_404_NOT_FOUND


async def test_upload_image(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_company_admin: Developer,
    session_user: User,
    session_campaign: Campaign,
    debug: Callable[[...], None],
) -> None:
    """Verify uploading an image asset creates an S3Asset record."""
    # When: Uploading a PNG image
    response = await client.post(
        build_url(
            Campaigns.ASSET_UPLOAD,
            company_id=session_company.id,
            campaign_id=session_campaign.id,
        ),
        headers=token_company_admin | {"On-Behalf-Of": str(session_user.id)},
        files={"upload": ("portrait.png", _png_bytes(), "image/png")},
    )
    # debug(response.json())

    # Then: Response is successful
    assert response.status_code == HTTP_201_CREATED

    response_json = response.json()

    # Then: Response contains expected fields with the detected image MIME type
    assert response_json["original_filename"] == "portrait.png"
    assert response_json["mime_type"] == "image/png"
    assert response_json["asset_type"] == "image"
    assert response_json["campaign_id"] == str(session_campaign.id)
    assert response_json["uploaded_by_id"] == str(session_user.id)
    assert response_json["company_id"] == str(session_company.id)
    assert response_json["id"] is not None

    expected_pattern = rf"^MOCK_URL/{session_company.id}/{session_campaign.id}/image/.+\.png$"
    assert re.match(expected_pattern, response_json["public_url"]) is not None

    # Then: Asset exists in the database
    db_asset = await S3Asset.filter(id=response_json["id"]).first()
    assert db_asset is not None
    assert db_asset.asset_type == AssetType.IMAGE
    assert db_asset.mime_type == "image/png"
    assert str(db_asset.campaign_id) == str(session_campaign.id)
    assert str(db_asset.company_id) == str(session_company.id)
    assert str(db_asset.uploaded_by_id) == str(session_user.id)
    assert db_asset.public_url == response_json["public_url"]


async def test_upload_svg_rejected(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_user: User,
    session_campaign: Campaign,
) -> None:
    """Verify uploading an SVG asset is rejected with a 400."""
    # When: Uploading an SVG file
    response = await client.post(
        build_url(
            Campaigns.ASSET_UPLOAD,
            company_id=session_company.id,
            campaign_id=session_campaign.id,
        ),
        headers=token_company_admin | {"On-Behalf-Of": str(session_user.id)},
        files={
            "upload": (
                "logo.svg",
                b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
                "image/svg+xml",
            )
        },
    )

    # Then: The upload is rejected and no asset is stored
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert await S3Asset.filter(campaign_id=session_campaign.id).count() == 0


async def test_upload_spoofed_image_rejected(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_user: User,
    session_campaign: Campaign,
) -> None:
    """Verify a non-image payload declared as an image is rejected with a 400."""
    # When: Uploading HTML bytes that claim to be a PNG
    response = await client.post(
        build_url(
            Campaigns.ASSET_UPLOAD,
            company_id=session_company.id,
            campaign_id=session_campaign.id,
        ),
        headers=token_company_admin | {"On-Behalf-Of": str(session_user.id)},
        files={"upload": ("evil.png", b"<html><script>alert(1)</script></html>", "image/png")},
    )

    # Then: The upload is rejected and no asset is stored
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert await S3Asset.filter(campaign_id=session_campaign.id).count() == 0


async def test_delete_image(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    session_company: Company,
    session_company_admin: Developer,
    session_user: User,
    session_campaign: Campaign,
    session_campaign_book: CampaignBook,
    s3asset_factory: Callable,
    debug: Callable[[...], None],
) -> None:
    """Verify deleting an asset removes it from S3 and the database."""
    # Given: A book with an asset
    asset = await s3asset_factory(
        book=session_campaign_book,
        uploaded_by=session_user,
        company=session_company,
    )

    # When: Deleting the asset
    response = await client.delete(
        build_url(
            Campaigns.BOOK_ASSET_DELETE,
            company_id=session_company.id,
            campaign_id=session_campaign.id,
            book_id=session_campaign_book.id,
            asset_id=asset.id,
        ),
        headers=token_company_admin | {"On-Behalf-Of": str(session_user.id)},
    )

    # Then: Response is successful
    assert response.status_code == HTTP_204_NO_CONTENT

    # And the asset is deleted from the database
    assert await S3Asset.filter(id=asset.id).first() is None
