"""Test AWS service."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from beanie import PydanticObjectId
from botocore.exceptions import ClientError

from vapi.config.base import settings
from vapi.constants import (
    AWS_ONE_DAY_CACHE_HEADER,
    AWS_ONE_HOUR_CACHE_HEADER,
    AWS_ONE_YEAR_CACHE_HEADER,
    AssetParentType,
    AssetType,
)
from vapi.db.models import S3Asset
from vapi.domain.services.aws_service import AWSS3Service
from vapi.lib.exceptions import AWSS3Error

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

    from vapi.db.models import (
        Campaign,
        CampaignBook,
        CampaignChapter,
        Character,
        Company,
        User,
    )

pytestmark = pytest.mark.anyio


class TestGenerateAwsKey:
    """Test the generate_aws_key method."""

    EXTENSION = "txt"
    FILENAME_PATTERN = re.compile(rf"^\d{{8}}T\d{{6}}[a-f0-9]{{32}}\.{EXTENSION}$")
    SPLIT_KEY_PATTERN = re.compile(r"^(.+)/(.+)$")

    async def test_generate_aws_key(
        self,
        debug: Callable[[...], None],
    ) -> None:
        """Test generating a full key for an object in the S3 bucket."""
        service = AWSS3Service()
        company_id = PydanticObjectId()
        parent_type = AssetParentType.CHARACTER
        parent_object_id = PydanticObjectId()
        asset_type = AssetType.IMAGE

        # When: Generating the AWS key
        aws_key = service._generate_aws_key(
            company_id=company_id,
            parent_type=parent_type,
            parent_object_id=parent_object_id,
            extension=self.EXTENSION,
            asset_type=asset_type,
        )
        # debug(aws_key)

        # Then: The key should be the expected value
        match = self.SPLIT_KEY_PATTERN.match(aws_key)
        assert match is not None
        key_prefix = match.group(1)
        filename = match.group(2)

        assert (
            key_prefix
            == f"{settings.aws.cloudfront_origin_path.rstrip('/')}/{company_id}/{parent_type.value}/{parent_object_id}/{asset_type.value}"
        )
        assert self.FILENAME_PATTERN.match(filename) is not None

    async def test_generate_aws_key_without_origin_path(self, debug: Callable[[...], None]) -> None:
        """Test generating a full key for an object in the S3 bucket without the origin path."""
        original_origin_path = settings.aws.cloudfront_origin_path
        settings.aws.cloudfront_origin_path = None

        service = AWSS3Service()
        company_id = PydanticObjectId()
        parent_type = AssetParentType.CHARACTER
        parent_object_id = PydanticObjectId()
        asset_type = AssetType.IMAGE

        # When: Generating the AWS key
        aws_key = service._generate_aws_key(
            company_id=company_id,
            parent_type=parent_type,
            parent_object_id=parent_object_id,
            extension=self.EXTENSION,
            asset_type=asset_type,
        )
        # debug(aws_key)

        # Then: The key should be the expected value
        match = self.SPLIT_KEY_PATTERN.match(aws_key)
        assert match is not None
        key_prefix = match.group(1)
        filename = match.group(2)

        assert (
            key_prefix == f"{company_id}/{parent_type.value}/{parent_object_id}/{asset_type.value}"
        )
        assert self.FILENAME_PATTERN.match(filename) is not None

        # Restore the original origin path to avoid affecting other tests
        settings.aws.cloudfront_origin_path = original_origin_path


class TestGetUrl:
    """Test the _generate_public_url method."""

    async def test__generate_public_url(self) -> None:
        """Test getting the URL for an object in the S3 bucket."""
        service = AWSS3Service()
        url = service._generate_public_url(key="test.txt")
        assert url == f"{settings.aws.cloudfront_url.rstrip('/')}/test.txt"

    async def test__generate_public_url_without_origin_path(self) -> None:
        """Test getting the URL for an object in the S3 bucket with the origin path."""
        service = AWSS3Service()
        url = service._generate_public_url(
            key=f"{settings.aws.cloudfront_origin_path.rstrip('/')}/something/1/test.txt"
        )
        assert url == f"{settings.aws.cloudfront_url.rstrip('/')}/something/1/test.txt"


class TestGetCacheControl:
    """Test the _get_cache_control method."""

    @pytest.mark.parametrize(
        "mime_type",
        [
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "image/svg+xml",
        ],
    )
    def test_get_cache_control_images(self, mime_type: str) -> None:
        """Verify image MIME types return 1 year cache with immutable."""
        # Given: An AWS S3 service
        service = AWSS3Service()

        # When: Getting cache control for an image
        result = service._get_cache_control(mime_type)

        # Then: Return aggressive 1 year caching
        assert result == AWS_ONE_YEAR_CACHE_HEADER

    @pytest.mark.parametrize(
        "mime_type",
        [
            "audio/mpeg",
            "audio/wav",
            "audio/ogg",
            "audio/mp3",
        ],
    )
    def test_get_cache_control_audio(self, mime_type: str) -> None:
        """Verify audio MIME types return 1 year cache with immutable."""
        # Given: An AWS S3 service
        service = AWSS3Service()

        # When: Getting cache control for audio
        result = service._get_cache_control(mime_type)

        # Then: Return aggressive 1 year caching
        assert result == AWS_ONE_YEAR_CACHE_HEADER

    @pytest.mark.parametrize(
        "mime_type",
        [
            "video/mp4",
            "video/webm",
            "video/quicktime",
            "video/avi",
        ],
    )
    def test_get_cache_control_video(self, mime_type: str) -> None:
        """Verify video MIME types return 1 year cache with immutable."""
        # Given: An AWS S3 service
        service = AWSS3Service()

        # When: Getting cache control for video
        result = service._get_cache_control(mime_type)

        # Then: Return aggressive 1 year caching
        assert result == AWS_ONE_YEAR_CACHE_HEADER

    @pytest.mark.parametrize(
        "mime_type",
        [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ],
    )
    def test_get_cache_control_documents(self, mime_type: str) -> None:
        """Verify document MIME types return 1 day cache."""
        # Given: An AWS S3 service
        service = AWSS3Service()

        # When: Getting cache control for a document
        result = service._get_cache_control(mime_type)

        # Then: Return 1 day caching
        assert result == AWS_ONE_DAY_CACHE_HEADER

    @pytest.mark.parametrize(
        "mime_type",
        [
            "application/octet-stream",
            "application/json",
            "application/xml",
            "text/plain",
            "text/html",
            "application/zip",
            "application/vnd.ms-excel",  # Doesn't match document patterns
        ],
    )
    def test_get_cache_control_default(self, mime_type: str) -> None:
        """Verify unrecognized MIME types return default 1 hour cache."""
        # Given: An AWS S3 service
        service = AWSS3Service()

        # When: Getting cache control for an unknown type
        result = service._get_cache_control(mime_type)

        # Then: Return default 1 hour caching
        assert result == AWS_ONE_HOUR_CACHE_HEADER


class TestUploadToS3:
    """Test the upload_to_s3 method."""


class TestUploadAsset:
    """Test the upload_asset method."""

    async def test_upload_asset_character(
        self,
        character_factory: Callable[..., Character],
        user_factory: Callable[..., User],
        base_company: Company,
    ) -> None:
        """Verify upload_asset creates S3Asset and attaches to Character."""
        # Given: A character and user
        user = await user_factory()
        character = await character_factory()

        # When: Uploading an asset
        service = AWSS3Service()
        asset = await service.upload_asset(
            parent=character,
            company_id=base_company.id,
            upload_user_id=user.id,
            data=b"test data",
            filename="test.jpg",
            mime_type="image/jpeg",
        )

        # Then: S3Asset is created with correct fields
        assert asset.id is not None
        assert asset.asset_type == AssetType.IMAGE
        assert asset.mime_type == "image/jpeg"
        assert asset.parent_type == AssetParentType.CHARACTER
        assert asset.parent_id == character.id
        assert asset.company_id == base_company.id
        assert asset.uploaded_by == user.id
        assert asset.s3_bucket == settings.aws.s3_bucket_name

        # Then: Character has the asset ID in asset_ids
        await character.sync()
        assert asset.id in character.asset_ids

    async def test_upload_asset_user(
        self,
        user_factory: Callable[..., User],
        base_company: Company,
    ) -> None:
        """Verify upload_asset creates S3Asset and attaches to User."""
        # Given: A user (as both parent and uploader)
        user = await user_factory()
        uploader = await user_factory()

        # When: Uploading an asset
        service = AWSS3Service()
        asset = await service.upload_asset(
            parent=user,
            company_id=base_company.id,
            upload_user_id=uploader.id,
            data=b"audio data",
            filename="song.mp3",
            mime_type="audio/mpeg",
        )

        # Then: S3Asset is created with correct fields
        assert asset.id is not None
        assert asset.asset_type == AssetType.AUDIO
        assert asset.mime_type == "audio/mpeg"
        assert asset.parent_type == AssetParentType.USER
        assert asset.parent_id == user.id
        assert asset.uploaded_by == uploader.id

        # Then: User has the asset ID in asset_ids
        await user.sync()
        assert asset.id in user.asset_ids

    async def test_upload_asset_campaign(
        self,
        campaign_factory: Callable[..., Campaign],
        user_factory: Callable[..., User],
        base_company: Company,
    ) -> None:
        """Verify upload_asset creates S3Asset and attaches to Campaign."""
        # Given: A campaign and user
        campaign = await campaign_factory()
        user = await user_factory()

        # When: Uploading an asset
        service = AWSS3Service()
        asset = await service.upload_asset(
            parent=campaign,
            company_id=base_company.id,
            upload_user_id=user.id,
            data=b"video data",
            filename="intro.mp4",
            mime_type="video/mp4",
        )

        # Then: S3Asset is created with correct fields
        assert asset.id is not None
        assert asset.asset_type == AssetType.VIDEO
        assert asset.mime_type == "video/mp4"
        assert asset.parent_type == AssetParentType.CAMPAIGN
        assert asset.parent_id == campaign.id

        # Then: Campaign has the asset ID in asset_ids
        await campaign.sync()
        assert asset.id in campaign.asset_ids

    async def test_upload_asset_campaign_book(
        self,
        campaign_book_factory: Callable[..., CampaignBook],
        user_factory: Callable[..., User],
        base_company: Company,
    ) -> None:
        """Verify upload_asset creates S3Asset and attaches to CampaignBook."""
        # Given: A campaign book and user
        book = await campaign_book_factory()
        user = await user_factory()

        # When: Uploading an asset
        service = AWSS3Service()
        asset = await service.upload_asset(
            parent=book,
            company_id=base_company.id,
            upload_user_id=user.id,
            data=b"pdf data",
            filename="document.pdf",
            mime_type="application/pdf",
        )

        # Then: S3Asset is created with correct fields
        assert asset.id is not None
        assert asset.asset_type == AssetType.DOCUMENT
        assert asset.mime_type == "application/pdf"
        assert asset.parent_type == AssetParentType.CAMPAIGN_BOOK
        assert asset.parent_id == book.id

        # Then: CampaignBook has the asset ID in asset_ids
        await book.sync()
        assert asset.id in book.asset_ids

    async def test_upload_asset_campaign_chapter(
        self,
        campaign_chapter_factory: Callable[..., CampaignChapter],
        user_factory: Callable[..., User],
        base_company: Company,
    ) -> None:
        """Verify upload_asset creates S3Asset and attaches to CampaignChapter."""
        # Given: A campaign chapter and user
        chapter = await campaign_chapter_factory()
        user = await user_factory()

        # When: Uploading an asset
        service = AWSS3Service()
        asset = await service.upload_asset(
            parent=chapter,
            company_id=base_company.id,
            upload_user_id=user.id,
            data=b"text data",
            filename="notes.txt",
            mime_type="text/plain",
        )

        # Then: S3Asset is created with correct fields
        assert asset.id is not None
        assert asset.asset_type == AssetType.TEXT
        assert asset.mime_type == "text/plain"
        assert asset.parent_type == AssetParentType.CAMPAIGN_CHAPTER
        assert asset.parent_id == chapter.id

        # Then: CampaignChapter has the asset ID in asset_ids
        await chapter.sync()
        assert asset.id in chapter.asset_ids

    @pytest.mark.parametrize(
        ("mime_type", "expected_type"),
        [
            ("image/jpeg", AssetType.IMAGE),
            ("image/png", AssetType.IMAGE),
            ("audio/mpeg", AssetType.AUDIO),
            ("video/mp4", AssetType.VIDEO),
            ("text/plain", AssetType.TEXT),
            ("application/pdf", AssetType.DOCUMENT),
            ("application/zip", AssetType.ARCHIVE),
            ("application/octet-stream", AssetType.OTHER),
        ],
    )
    async def test_upload_asset_determines_asset_type(
        self,
        character_factory: Callable[..., Character],
        user_factory: Callable[..., User],
        base_company: Company,
        mime_type: str,
        expected_type: AssetType,
    ) -> None:
        """Verify upload_asset sets correct AssetType based on MIME type."""
        # Given: A character and user
        character = await character_factory()
        user = await user_factory()

        # When: Uploading an asset with the given MIME type
        service = AWSS3Service()
        asset = await service.upload_asset(
            parent=character,
            company_id=base_company.id,
            upload_user_id=user.id,
            data=b"test data",
            filename="test.bin",
            mime_type=mime_type,
        )

        # Then: Asset type is correctly determined
        assert asset.asset_type == expected_type

    async def test_upload_asset_sanitizes_filename(
        self,
        character_factory: Callable[..., Character],
        user_factory: Callable[..., User],
        base_company: Company,
    ) -> None:
        """Verify upload_asset sanitizes dangerous characters in filename."""
        # Given: A character, user, and dangerous filename
        character = await character_factory()
        user = await user_factory()
        dangerous_filename = '../path/to/file"name;test.jpg'

        # When: Uploading an asset with a dangerous filename
        service = AWSS3Service()
        asset = await service.upload_asset(
            parent=character,
            company_id=base_company.id,
            upload_user_id=user.id,
            data=b"test data",
            filename=dangerous_filename,
            mime_type="image/jpeg",
        )

        # Then: Filename is sanitized (dangerous chars removed)
        assert ".." not in asset.original_filename
        assert "/" not in asset.original_filename
        assert '"' not in asset.original_filename
        assert ";" not in asset.original_filename


class TestDeleteObjectFromS3:
    """Test the _delete_object_from_s3 method."""

    def test_delete_object_from_s3_success(self, mocker: MockerFixture) -> None:
        """Verify _delete_object_from_s3 succeeds when S3 returns DeleteMarker True."""
        # Given: A mocked S3 client that returns DeleteMarker True
        mock_s3_client = mocker.MagicMock()
        mock_s3_client.get_bucket_location.return_value = {"LocationConstraint": "us-east-1"}
        mock_s3_client.delete_object.return_value = {"DeleteMarker": True}
        mocker.patch("vapi.domain.services.aws_service.boto3.client", return_value=mock_s3_client)

        # When: Deleting an object
        service = AWSS3Service()
        service._delete_object_from_s3(key="test-key")

        # Then: delete_object was called with correct parameters
        mock_s3_client.delete_object.assert_called_once_with(
            Bucket=settings.aws.s3_bucket_name, Key="test-key"
        )

    def test_delete_object_from_s3_raises_on_client_error(self, mocker: MockerFixture) -> None:
        """Verify _delete_object_from_s3 raises AWSS3Error on ClientError."""
        # Given: A mocked S3 client that raises ClientError
        mock_s3_client = mocker.MagicMock()
        mock_s3_client.get_bucket_location.return_value = {"LocationConstraint": "us-east-1"}
        mock_s3_client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Error"}}, "DeleteObject"
        )
        mocker.patch("vapi.domain.services.aws_service.boto3.client", return_value=mock_s3_client)

        # When/Then: Deleting raises AWSS3Error
        service = AWSS3Service()
        with pytest.raises(AWSS3Error, match="Failed to delete object from AWS S3"):
            service._delete_object_from_s3(key="test-key")


class TestDeleteAsset:
    """Test the delete_asset method."""

    async def test_delete_asset_without_parent(
        self,
        character_factory: Callable[..., Character],
        user_factory: Callable[..., User],
        s3asset_factory: Callable[..., S3Asset],
        base_company: Company,
        mocker: MockerFixture,
    ) -> None:
        """Verify delete_asset removes asset from S3 and archives it."""
        # Given: A character with an asset
        asset = await s3asset_factory(parent_type=AssetParentType.UNKNOWN, parent_id=None)

        # Patch the S3 deletion
        mocker.patch.object(AWSS3Service, "_delete_object_from_s3")

        # When: Deleting the asset
        service = AWSS3Service()
        result = await service.delete_asset(asset)

        # Then: Asset is archived and removed from character
        assert result is True
        assert await S3Asset.get(asset.id) is None

    async def test_delete_asset_character(
        self,
        character_factory: Callable[..., Character],
        user_factory: Callable[..., User],
        s3asset_factory: Callable[..., S3Asset],
        base_company: Company,
        mocker: MockerFixture,
    ) -> None:
        """Verify delete_asset removes asset from Character and archives it."""
        # Given: A character with an asset
        user = await user_factory()
        character = await character_factory()

        asset = await s3asset_factory(
            asset_type=AssetType.IMAGE,
            mime_type="image/jpeg",
            original_filename="test.jpg",
            parent_type=AssetParentType.CHARACTER,
            parent_id=character.id,
            company_id=base_company.id,
            uploaded_by=user.id,
            s3_key="test-key",
            s3_bucket="test-bucket",
            public_url="https://example.com/test.jpg",
        )

        character.asset_ids = [asset.id]
        await character.save()

        # Patch the S3 deletion
        mocker.patch.object(AWSS3Service, "_delete_object_from_s3")

        # When: Deleting the asset
        service = AWSS3Service()
        result = await service.delete_asset(asset)

        # Then: Asset is archived and removed from character
        assert result is True
        assert await S3Asset.get(asset.id) is None
        await character.sync()
        assert asset.id not in character.asset_ids

    async def test_delete_asset_user(
        self,
        user_factory: Callable[..., User],
        s3asset_factory: Callable[..., S3Asset],
        base_company: Company,
        mocker: MockerFixture,
    ) -> None:
        """Verify delete_asset removes asset from User and archives it."""
        # Given: A user with an asset
        user = await user_factory()
        uploader = await user_factory()

        asset = await s3asset_factory(
            asset_type=AssetType.IMAGE,
            mime_type="image/jpeg",
            original_filename="test.jpg",
            parent_type=AssetParentType.USER,
            parent_id=user.id,
            company_id=base_company.id,
            uploaded_by=uploader.id,
            s3_key="test-key",
            s3_bucket="test-bucket",
            public_url="https://example.com/test.jpg",
        )

        user.asset_ids = [asset.id]
        await user.save()

        # Patch the S3 deletion
        mocker.patch.object(AWSS3Service, "_delete_object_from_s3")

        # When: Deleting the asset
        service = AWSS3Service()
        result = await service.delete_asset(asset)

        # Then: Asset is archived and removed from user
        assert result is True
        assert await S3Asset.get(asset.id) is None
        await user.sync()
        assert asset.id not in user.asset_ids

    async def test_delete_asset_campaign(
        self,
        campaign_factory: Callable[..., Campaign],
        user_factory: Callable[..., User],
        s3asset_factory: Callable[..., S3Asset],
        base_company: Company,
        mocker: MockerFixture,
    ) -> None:
        """Verify delete_asset removes asset from Campaign and archives it."""
        # Given: A campaign with an asset
        campaign = await campaign_factory()
        user = await user_factory()

        asset = await s3asset_factory(
            asset_type=AssetType.IMAGE,
            mime_type="image/jpeg",
            original_filename="test.jpg",
            parent_type=AssetParentType.CAMPAIGN,
            parent_id=campaign.id,
            company_id=base_company.id,
            uploaded_by=user.id,
            s3_key="test-key",
            s3_bucket="test-bucket",
            public_url="https://example.com/test.jpg",
        )

        campaign.asset_ids = [asset.id]
        await campaign.save()

        # Patch the S3 deletion
        mocker.patch.object(AWSS3Service, "_delete_object_from_s3")

        # When: Deleting the asset
        service = AWSS3Service()
        result = await service.delete_asset(asset)

        # Then: Asset is archived and removed from campaign
        assert result is True
        assert await S3Asset.get(asset.id) is None
        await campaign.sync()
        assert asset.id not in campaign.asset_ids

    async def test_delete_asset_raises_on_s3_error(
        self,
        character_factory: Callable[..., Character],
        user_factory: Callable[..., User],
        s3asset_factory: Callable[..., S3Asset],
        base_company: Company,
        mocker: MockerFixture,
    ) -> None:
        """Verify delete_asset raises AWSS3Error when S3 deletion fails."""
        # Given: A character with an asset
        user = await user_factory()
        character = await character_factory()

        asset = await s3asset_factory(
            asset_type=AssetType.IMAGE,
            mime_type="image/jpeg",
            original_filename="test.jpg",
            parent_type=AssetParentType.CHARACTER,
            parent_id=character.id,
            company_id=base_company.id,
            uploaded_by=user.id,
            s3_key="test-key",
            s3_bucket="test-bucket",
            public_url="https://example.com/test.jpg",
        )

        character.asset_ids = [asset.id]
        await character.save()

        # Patch the S3 deletion to raise an error
        mocker.patch.object(
            AWSS3Service,
            "_delete_object_from_s3",
            side_effect=AWSS3Error(detail="S3 deletion failed"),
        )

        # When/Then: Deleting raises AWSS3Error
        service = AWSS3Service()
        with pytest.raises(AWSS3Error):
            await service.delete_asset(asset)
