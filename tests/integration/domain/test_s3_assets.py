"""Test S3 asset controllers (Tortoise ORM)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_404_NOT_FOUND,
)

from vapi.constants import AssetType
from vapi.db.sql_models.aws import S3Asset
from vapi.domain.urls import Campaigns, Characters, Users

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.campaign import Campaign as PgCampaign
    from vapi.db.sql_models.campaign import CampaignBook as PgCampaignBook
    from vapi.db.sql_models.campaign import CampaignChapter as PgCampaignChapter
    from vapi.db.sql_models.company import Company as PgCompany
    from vapi.db.sql_models.developer import Developer as PgDeveloper
    from vapi.db.sql_models.user import User as PgUser

pytestmark = pytest.mark.anyio


async def test_list_assets(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    pg_mirror_company: PgCompany,
    pg_mirror_company_admin: PgDeveloper,
    pg_mirror_user: PgUser,
    pg_mirror_campaign: PgCampaign,
    pg_character_factory: Callable,
    pg_s3asset_factory: Callable,
    debug: Callable[[...], None],
) -> None:
    """Verify listing assets filtered by type returns correct results."""
    # Given: A character with image assets and a text asset
    character = await pg_character_factory(
        company=pg_mirror_company,
        user_player=pg_mirror_user,
        user_creator=pg_mirror_user,
        campaign=pg_mirror_campaign,
    )
    image_assets = []
    for _ in range(3):
        asset = await pg_s3asset_factory(
            asset_type=AssetType.IMAGE,
            uploaded_by=pg_mirror_user,
            character=character,
            company=pg_mirror_company,
        )
        image_assets.append(asset)

    # And a text asset that should not be returned when filtering by IMAGE
    await pg_s3asset_factory(
        asset_type=AssetType.TEXT,
        uploaded_by=pg_mirror_user,
        character=character,
        company=pg_mirror_company,
    )

    # And an unrelated asset (no character FK)
    await pg_s3asset_factory(
        asset_type=AssetType.IMAGE,
        uploaded_by=pg_mirror_user,
        company=pg_mirror_company,
    )

    # When: Listing assets filtered by IMAGE type
    response = await client.get(
        build_url(
            Characters.ASSETS,
            company_id=pg_mirror_company.id,
            user_id=pg_mirror_user.id,
            character_id=character.id,
        ),
        headers=token_company_admin,
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
    pg_mirror_company: PgCompany,
    pg_mirror_company_admin: PgDeveloper,
    pg_mirror_user: PgUser,
    pg_s3asset_factory: Callable,
    debug: Callable[[...], None],
) -> None:
    """Verify getting a single user asset returns correct data."""
    # Given: A user with an asset
    asset = await pg_s3asset_factory(
        asset_type=AssetType.TEXT,
        uploaded_by=pg_mirror_user,
        user_parent=pg_mirror_user,
        company=pg_mirror_company,
    )

    # When: Getting the asset
    response = await client.get(
        build_url(
            Users.ASSET_DETAIL,
            company_id=pg_mirror_company.id,
            user_id=pg_mirror_user.id,
            asset_id=asset.id,
        ),
        headers=token_company_admin,
    )
    # debug(response.json())

    # Then: Response is successful
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == str(asset.id)
    assert response_json["asset_type"] == AssetType.TEXT.value
    assert response_json["user_parent_id"] == str(pg_mirror_user.id)


async def test_get_asset_not_parent(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    pg_mirror_company: PgCompany,
    pg_mirror_company_admin: PgDeveloper,
    pg_mirror_user: PgUser,
    pg_mirror_campaign: PgCampaign,
    pg_mirror_campaign_book: PgCampaignBook,
    pg_mirror_campaign_chapter: PgCampaignChapter,
    pg_s3asset_factory: Callable,
    debug: Callable[[...], None],
) -> None:
    """Verify getting an asset with wrong parent returns 404."""
    # Given: An asset belonging to a different chapter (mismatched FK)
    asset = await pg_s3asset_factory(
        asset_type=AssetType.TEXT,
        chapter=None,
        company=pg_mirror_company,
        uploaded_by=pg_mirror_user,
    )

    # When: Getting the asset via the chapter's URL
    response = await client.get(
        build_url(
            Campaigns.CHAPTER_ASSET_DETAIL,
            company_id=pg_mirror_company.id,
            campaign_id=pg_mirror_campaign.id,
            book_id=pg_mirror_campaign_book.id,
            chapter_id=pg_mirror_campaign_chapter.id,
            asset_id=asset.id,
        ),
        headers=token_company_admin,
    )

    # Then: Response is 404
    assert response.status_code == HTTP_404_NOT_FOUND


async def test_upload_image(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    pg_mirror_company: PgCompany,
    pg_mirror_company_admin: PgDeveloper,
    pg_mirror_user: PgUser,
    pg_mirror_campaign: PgCampaign,
    debug: Callable[[...], None],
) -> None:
    """Verify uploading an asset creates an S3Asset record."""
    # When: Uploading a file
    response = await client.post(
        build_url(
            Campaigns.ASSET_UPLOAD,
            company_id=pg_mirror_company.id,
            campaign_id=pg_mirror_campaign.id,
            user_id=pg_mirror_user.id,
        ),
        headers=token_company_admin,
        files={"upload": ("somefile.txt", b"world")},
    )
    # debug(response.json())

    # Then: Response is successful
    assert response.status_code == HTTP_201_CREATED

    response_json = response.json()

    # Then: Response contains expected fields
    assert response_json["original_filename"] == "somefile.txt"
    assert response_json["mime_type"] == "text/plain"
    assert response_json["asset_type"] == "text"
    assert response_json["campaign_id"] == str(pg_mirror_campaign.id)
    assert response_json["uploaded_by_id"] == str(pg_mirror_user.id)
    assert response_json["company_id"] == str(pg_mirror_company.id)
    assert response_json["id"] is not None

    expected_pattern = rf"^MOCK_URL/{pg_mirror_company.id}/{pg_mirror_campaign.id}/text/.+\.txt$"
    assert re.match(expected_pattern, response_json["public_url"]) is not None

    # Then: Asset exists in the database
    db_asset = await S3Asset.filter(id=response_json["id"]).first()
    assert db_asset is not None
    assert db_asset.asset_type == AssetType.TEXT
    assert db_asset.mime_type == "text/plain"
    assert str(db_asset.campaign_id) == str(pg_mirror_campaign.id)  # type: ignore[attr-defined]
    assert str(db_asset.company_id) == str(pg_mirror_company.id)  # type: ignore[attr-defined]
    assert str(db_asset.uploaded_by_id) == str(pg_mirror_user.id)  # type: ignore[attr-defined]
    assert db_asset.public_url == response_json["public_url"]


async def test_delete_image(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    build_url: Callable[[str, Any], str],
    pg_mirror_company: PgCompany,
    pg_mirror_company_admin: PgDeveloper,
    pg_mirror_user: PgUser,
    pg_mirror_campaign: PgCampaign,
    pg_mirror_campaign_book: PgCampaignBook,
    pg_s3asset_factory: Callable,
    debug: Callable[[...], None],
) -> None:
    """Verify deleting an asset removes it from S3 and the database."""
    # Given: A book with an asset
    asset = await pg_s3asset_factory(
        book=pg_mirror_campaign_book,
        uploaded_by=pg_mirror_user,
        company=pg_mirror_company,
    )

    # When: Deleting the asset
    response = await client.delete(
        build_url(
            Campaigns.BOOK_ASSET_DELETE,
            company_id=pg_mirror_company.id,
            user_id=pg_mirror_user.id,
            campaign_id=pg_mirror_campaign.id,
            book_id=pg_mirror_campaign_book.id,
            asset_id=asset.id,
        ),
        headers=token_company_admin,
    )

    # Then: Response is successful
    assert response.status_code == HTTP_204_NO_CONTENT

    # And the asset is deleted from the database
    assert await S3Asset.filter(id=asset.id).first() is None
