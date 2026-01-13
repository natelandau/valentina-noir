"""Test images."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from beanie import PydanticObjectId
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_404_NOT_FOUND,
)

from vapi.constants import AssetType
from vapi.db.models import S3Asset
from vapi.domain.urls import Campaigns, Characters, Users

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.models import Campaign, CampaignBook, CampaignChapter, Character, Company, User

pytestmark = pytest.mark.anyio


EXCLUDE_ASSET_FIELDS = {
    "s3_key",
    "s3_bucket",
    "is_archived",
    "archive_date",
}


async def test_list_assets(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    base_company: Company,
    build_url: Callable[[str, ...], str],
    character_factory: Callable[[...], Character],
    user_factory: Callable[[...], User],
    debug: Callable[[...], None],
) -> None:
    """Test listing assets."""
    user = await user_factory()
    character = await character_factory()
    assets = []
    for i in range(3):
        asset = await S3Asset(
            asset_type=AssetType.IMAGE,
            mime_type="image/jpeg",
            original_filename=f"somefile{i}.jpg",
            parent_type="character",
            parent_id=character.id,
            company_id=base_company.id,
            uploaded_by=user.id,
            public_url=f"https://example.com/somefile{i}.jpg",
            s3_key="test-key",
            s3_bucket="test-bucket",
        ).insert()
        assets.append(asset)
        character.asset_ids.append(asset.id)

    # And assets that should not be returned
    asset = await S3Asset(
        asset_type=AssetType.TEXT,
        mime_type="image/jpeg",
        original_filename="somefile.txt",
        parent_type="character",
        parent_id=character.id,
        company_id=base_company.id,
        uploaded_by=user.id,
        public_url="https://example.com/somefile.txt",
        s3_key="test-key",
        s3_bucket="test-bucket",
    ).insert()
    character.asset_ids.append(asset.id)
    await character.save()

    await S3Asset(
        asset_type=AssetType.IMAGE,
        mime_type="image/jpeg",
        original_filename="somefile.jpg",
        parent_type="character",
        parent_id=PydanticObjectId(),
        company_id=base_company.id,
        uploaded_by=user.id,
        public_url="https://example.com/somefile.jpg",
        s3_key="test-key",
        s3_bucket="test-bucket",
    ).insert()

    # When: Listing assets
    response = await client.get(
        build_url(Characters.ASSETS, character_id=character.id),
        headers=token_company_admin,
        params={"asset_type": AssetType.IMAGE.value},
    )
    # debug(response.json())

    # Then: Response is successful
    assert response.status_code == HTTP_200_OK

    # Then: Response contains expected fields
    response_json = response.json()
    assert len(response_json["items"]) == 3
    assert response_json["items"] == [
        asset.model_dump(mode="json", exclude=EXCLUDE_ASSET_FIELDS) for asset in assets
    ]
    assert response_json["limit"] == 10
    assert response_json["offset"] == 0
    assert response_json["total"] == 3


async def test_get_asset(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    base_company: Company,
    build_url: Callable[[str, ...], str],
    user_factory: Callable[[...], User],
    debug: Callable[[...], None],
) -> None:
    """Get an asset."""
    user = await user_factory()
    asset = await S3Asset(
        asset_type=AssetType.TEXT,
        mime_type="text/plain",
        original_filename="somefile.txt",
        parent_type="user",
        parent_id=user.id,
        company_id=base_company.id,
        uploaded_by=user.id,
        public_url="https://example.com/somefile.txt",
        s3_key="test-key",
        s3_bucket="test-bucket",
    ).insert()
    user.asset_ids = [asset.id]
    await user.save()

    # When: Getting an asset
    response = await client.get(
        build_url(Users.ASSET_DETAIL, user_id=user.id, asset_id=asset.id),
        headers=token_company_admin,
    )
    # debug(response.json())

    # Then: Response is successful
    assert response.status_code == HTTP_200_OK
    assert response.json() == asset.model_dump(mode="json", exclude=EXCLUDE_ASSET_FIELDS)


async def test_get_asset_not_parent(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    base_company: Company,
    build_url: Callable[[str, ...], str],
    campaign_chapter_factory: Callable[[...], CampaignChapter],
    user_factory: Callable[[...], User],
    debug: Callable[[...], None],
) -> None:
    """Verify getting an asset that is not the parent."""
    user = await user_factory()
    campaign_chapter = await campaign_chapter_factory()
    asset = await S3Asset(
        asset_type=AssetType.TEXT,
        mime_type="text/plain",
        original_filename="somefile.txt",
        parent_type="campaignchapter",
        parent_id=PydanticObjectId(),
        company_id=base_company.id,
        uploaded_by=user.id,
        public_url="https://example.com/somefile.txt",
        s3_key="test-key",
        s3_bucket="test-bucket",
    ).insert()
    campaign_chapter.asset_ids = [asset.id]
    await campaign_chapter.save()

    # When: Getting an asset
    response = await client.get(
        build_url(
            Campaigns.CHAPTER_ASSET_DETAIL,
            chapter_id=campaign_chapter.id,
            asset_id=asset.id,
        ),
        headers=token_company_admin,
    )
    # debug(response.json())

    # Then: Response is successful
    assert response.status_code == HTTP_404_NOT_FOUND


async def test_upload_image(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    base_company: Company,
    campaign_factory: Callable[[...], Campaign],
    build_url: Callable[[str, ...], str],
    debug: Callable[[...], None],
    user_factory: Callable[[...], User],
) -> None:
    """Test uploading an image."""
    # Given: A user and character
    user = await user_factory()
    campaign = await campaign_factory()

    # When: Uploading an image
    response = await client.post(
        build_url(Campaigns.ASSET_UPLOAD, campaign_id=campaign.id, user_id=user.id),
        headers=token_company_admin,
        files={"upload": ("somefile.txt", b"world")},
    )

    # Then: Response is successful
    assert response.status_code == HTTP_201_CREATED

    response_json = response.json()

    # Then: Response contains expected fields
    assert response_json["original_filename"] == "somefile.txt"
    assert response_json["mime_type"] == "text/plain"
    assert response_json["asset_type"] == "text"
    assert response_json["parent_type"] == "campaign"
    assert response_json["parent_id"] == str(campaign.id)
    assert response_json["uploaded_by"] == str(user.id)
    assert response_json["company_id"] == str(campaign.company_id)
    assert response_json["id"] is not None

    expected_pattern = rf"^MOCK_URL/{campaign.company_id}/campaign/{campaign.id}/text/.+\.txt$"
    assert re.match(expected_pattern, response_json["public_url"]) is not None

    # Then: Character has the aws file
    await campaign.sync()
    assert campaign.asset_ids == [PydanticObjectId(response_json["id"])]

    db_asset = await S3Asset.get(response_json["id"])
    assert db_asset is not None
    assert db_asset.id == PydanticObjectId(response_json["id"])
    assert db_asset.asset_type == AssetType.TEXT
    assert db_asset.mime_type == "text/plain"
    assert db_asset.parent_type == "campaign"
    assert db_asset.parent_id == campaign.id
    assert db_asset.company_id == campaign.company_id
    assert db_asset.uploaded_by == user.id
    assert db_asset.public_url == response_json["public_url"]


async def test_delete_image(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    base_company: Company,
    build_url: Callable[[str, ...], str],
    debug: Callable[[...], None],
    campaign_book_factory: Callable[[...], CampaignBook],
    user_factory: Callable[[...], User],
) -> None:
    """Test deleting an image."""
    # Given: A user and character
    user = await user_factory()
    book = await campaign_book_factory()
    asset = await S3Asset(
        asset_type=AssetType.TEXT,
        mime_type="text/plain",
        original_filename="somefile.txt",
        parent_type="campaignbook",
        parent_id=book.id,
        company_id=base_company.id,
        uploaded_by=user.id,
        public_url="https://example.com/somefile.txt",
        s3_key="test-key",
        s3_bucket="test-bucket",
    ).insert()
    book.asset_ids = [asset.id]
    await book.save()

    # When deleting an asset
    response = await client.delete(
        build_url(Campaigns.BOOK_ASSET_DELETE, book_id=book.id, asset_id=asset.id),
        headers=token_company_admin,
    )

    # Then: Response is successful
    assert response.status_code == HTTP_204_NO_CONTENT

    # Then: Character has no assets
    await book.sync()
    assert book.asset_ids == []

    # And the asset is archived
    await asset.sync()
    assert asset.is_archived
