"""Test AWS service."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from vapi.config.base import settings
from vapi.constants import (
    AWS_ONE_DAY_CACHE_HEADER,
    AWS_ONE_HOUR_CACHE_HEADER,
    AWS_ONE_YEAR_CACHE_HEADER,
    AssetType,
)
from vapi.db.sql_models.aws import S3Asset
from vapi.domain.services.aws_service import AWSS3Service
from vapi.lib.exceptions import AWSS3Error

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

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
        """Verify generating a full key for an object in the S3 bucket."""
        service = AWSS3Service()
        company_id = uuid4()
        parent_id = uuid4()
        asset_type = AssetType.IMAGE

        # When: Generating the AWS key
        aws_key = service._generate_aws_key(
            company_id=company_id,
            parent_id=parent_id,
            extension=self.EXTENSION,
            asset_type=asset_type,
        )

        # Then: The key should be the expected value
        match = self.SPLIT_KEY_PATTERN.match(aws_key)
        assert match is not None
        key_prefix = match.group(1)
        filename = match.group(2)

        assert (
            key_prefix
            == f"{settings.aws.cloudfront_origin_path.rstrip('/')}/{company_id}/{parent_id}/{asset_type.value}"
        )
        assert self.FILENAME_PATTERN.match(filename) is not None

    async def test_generate_aws_key_without_origin_path(self, debug: Callable[[...], None]) -> None:
        """Verify generating a full key without the origin path."""
        original_origin_path = settings.aws.cloudfront_origin_path
        settings.aws.cloudfront_origin_path = None

        service = AWSS3Service()
        company_id = uuid4()
        parent_id = uuid4()
        asset_type = AssetType.IMAGE

        # When: Generating the AWS key
        aws_key = service._generate_aws_key(
            company_id=company_id,
            parent_id=parent_id,
            extension=self.EXTENSION,
            asset_type=asset_type,
        )

        # Then: The key should be the expected value
        match = self.SPLIT_KEY_PATTERN.match(aws_key)
        assert match is not None
        key_prefix = match.group(1)
        filename = match.group(2)

        assert key_prefix == f"{company_id}/{parent_id}/{asset_type.value}"
        assert self.FILENAME_PATTERN.match(filename) is not None

        # Restore the original origin path to avoid affecting other tests
        settings.aws.cloudfront_origin_path = original_origin_path


class TestGetUrl:
    """Test the _generate_public_url method."""

    async def test__generate_public_url(self) -> None:
        """Verify getting the URL for an object in the S3 bucket."""
        service = AWSS3Service()
        url = service._generate_public_url(key="test.txt")
        assert url == f"{settings.aws.cloudfront_url.rstrip('/')}/test.txt"

    async def test__generate_public_url_without_origin_path(self) -> None:
        """Verify getting the URL with the origin path stripped."""
        service = AWSS3Service()
        url = service._generate_public_url(
            key=f"{settings.aws.cloudfront_origin_path.rstrip('/')}/something/1/test.txt"
        )
        assert url == f"{settings.aws.cloudfront_url.rstrip('/')}/something/1/test.txt"


class TestGetCacheControl:
    """Test the _get_cache_control method."""

    @pytest.mark.parametrize(
        "asset_type",
        [AssetType.IMAGE, AssetType.AUDIO, AssetType.VIDEO],
    )
    def test_get_cache_control_long_lived(self, asset_type: AssetType) -> None:
        """Verify image, audio, and video assets return 1 year cache."""
        # Given: An AWS S3 service
        service = AWSS3Service()

        # When: Getting cache control for a long-lived asset type
        result = service._get_cache_control(asset_type)

        # Then: Return aggressive 1 year caching
        assert result == AWS_ONE_YEAR_CACHE_HEADER

    def test_get_cache_control_documents(self) -> None:
        """Verify document assets return 1 day cache."""
        # Given: An AWS S3 service
        service = AWSS3Service()

        # When: Getting cache control for a document
        result = service._get_cache_control(AssetType.DOCUMENT)

        # Then: Return 1 day caching
        assert result == AWS_ONE_DAY_CACHE_HEADER

    @pytest.mark.parametrize(
        "asset_type",
        [AssetType.TEXT, AssetType.ARCHIVE, AssetType.OTHER],
    )
    def test_get_cache_control_default(self, asset_type: AssetType) -> None:
        """Verify other asset types return default 1 hour cache."""
        # Given: An AWS S3 service
        service = AWSS3Service()

        # When: Getting cache control for an unrecognized type
        result = service._get_cache_control(asset_type)

        # Then: Return default 1 hour caching
        assert result == AWS_ONE_HOUR_CACHE_HEADER


class TestUploadToS3:
    """Test the upload_to_s3 method."""


class TestUploadAsset:
    """Test the upload_asset method."""

    async def test_upload_asset_character(
        self,
        character_factory: Callable,
        user_factory: Callable,
        company_factory: Callable,
    ) -> None:
        """Verify upload_asset creates S3Asset with character FK."""
        # Given: A character and user
        company = await company_factory()
        user = await user_factory(company=company)
        character = await character_factory(company=company)

        # When: Uploading an asset
        service = AWSS3Service()
        asset = await service.upload_asset(
            company_id=company.id,
            uploaded_by_id=user.id,
            parent_id=character.id,
            parent_fk_field="character_id",
            data=b"test data",
            filename="test.jpg",
            mime_type="image/jpeg",
        )

        # Then: S3Asset is created with correct fields
        assert asset.id is not None
        assert asset.asset_type == AssetType.IMAGE
        assert asset.mime_type == "image/jpeg"
        assert asset.character_id == character.id  # type: ignore[attr-defined]
        assert asset.company_id == company.id  # type: ignore[attr-defined]
        assert asset.uploaded_by_id == user.id  # type: ignore[attr-defined]
        assert asset.s3_bucket == settings.aws.s3_bucket_name

    async def test_upload_asset_user(
        self,
        user_factory: Callable,
        company_factory: Callable,
    ) -> None:
        """Verify upload_asset creates S3Asset with user_parent FK."""
        # Given: A user (as both parent and uploader)
        company = await company_factory()
        user = await user_factory(company=company)
        uploader = await user_factory(company=company)

        # When: Uploading an asset
        service = AWSS3Service()
        asset = await service.upload_asset(
            company_id=company.id,
            uploaded_by_id=uploader.id,
            parent_id=user.id,
            parent_fk_field="user_parent_id",
            data=b"audio data",
            filename="song.mp3",
            mime_type="audio/mpeg",
        )

        # Then: S3Asset is created with correct fields
        assert asset.id is not None
        assert asset.asset_type == AssetType.AUDIO
        assert asset.mime_type == "audio/mpeg"
        assert asset.user_parent_id == user.id  # type: ignore[attr-defined]
        assert asset.uploaded_by_id == uploader.id  # type: ignore[attr-defined]

    async def test_upload_asset_campaign(
        self,
        campaign_factory: Callable,
        user_factory: Callable,
        company_factory: Callable,
    ) -> None:
        """Verify upload_asset creates S3Asset with campaign FK."""
        # Given: A campaign and user
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        user = await user_factory(company=company)

        # When: Uploading an asset
        service = AWSS3Service()
        asset = await service.upload_asset(
            company_id=company.id,
            uploaded_by_id=user.id,
            parent_id=campaign.id,
            parent_fk_field="campaign_id",
            data=b"video data",
            filename="intro.mp4",
            mime_type="video/mp4",
        )

        # Then: S3Asset is created with correct fields
        assert asset.id is not None
        assert asset.asset_type == AssetType.VIDEO
        assert asset.mime_type == "video/mp4"
        assert asset.campaign_id == campaign.id  # type: ignore[attr-defined]

    async def test_upload_asset_campaign_book(
        self,
        campaign_book_factory: Callable,
        campaign_factory: Callable,
        user_factory: Callable,
        company_factory: Callable,
    ) -> None:
        """Verify upload_asset creates S3Asset with book FK."""
        # Given: A campaign book and user
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(campaign=campaign)
        user = await user_factory(company=company)

        # When: Uploading an asset
        service = AWSS3Service()
        asset = await service.upload_asset(
            company_id=company.id,
            uploaded_by_id=user.id,
            parent_id=book.id,
            parent_fk_field="book_id",
            data=b"pdf data",
            filename="document.pdf",
            mime_type="application/pdf",
        )

        # Then: S3Asset is created with correct fields
        assert asset.id is not None
        assert asset.asset_type == AssetType.DOCUMENT
        assert asset.mime_type == "application/pdf"
        assert asset.book_id == book.id  # type: ignore[attr-defined]

    async def test_upload_asset_campaign_chapter(
        self,
        campaign_chapter_factory: Callable,
        campaign_book_factory: Callable,
        campaign_factory: Callable,
        user_factory: Callable,
        company_factory: Callable,
    ) -> None:
        """Verify upload_asset creates S3Asset with chapter FK."""
        # Given: A campaign chapter and user
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        book = await campaign_book_factory(campaign=campaign)
        chapter = await campaign_chapter_factory(book=book)
        user = await user_factory(company=company)

        # When: Uploading an asset
        service = AWSS3Service()
        asset = await service.upload_asset(
            company_id=company.id,
            uploaded_by_id=user.id,
            parent_id=chapter.id,
            parent_fk_field="chapter_id",
            data=b"text data",
            filename="notes.txt",
            mime_type="text/plain",
        )

        # Then: S3Asset is created with correct fields
        assert asset.id is not None
        assert asset.asset_type == AssetType.TEXT
        assert asset.mime_type == "text/plain"
        assert asset.chapter_id == chapter.id  # type: ignore[attr-defined]

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
        character_factory: Callable,
        user_factory: Callable,
        company_factory: Callable,
        mime_type: str,
        expected_type: AssetType,
    ) -> None:
        """Verify upload_asset sets correct AssetType based on MIME type."""
        # Given: A character and user
        company = await company_factory()
        character = await character_factory(company=company)
        user = await user_factory(company=company)

        # When: Uploading an asset with the given MIME type
        service = AWSS3Service()
        asset = await service.upload_asset(
            company_id=company.id,
            uploaded_by_id=user.id,
            parent_id=character.id,
            parent_fk_field="character_id",
            data=b"test data",
            filename="test.bin",
            mime_type=mime_type,
        )

        # Then: Asset type is correctly determined
        assert asset.asset_type == expected_type

    async def test_upload_asset_sanitizes_filename(
        self,
        character_factory: Callable,
        user_factory: Callable,
        company_factory: Callable,
    ) -> None:
        """Verify upload_asset sanitizes dangerous characters in filename."""
        # Given: A character, user, and dangerous filename
        company = await company_factory()
        character = await character_factory(company=company)
        user = await user_factory(company=company)
        dangerous_filename = '../path/to/file"name;test.jpg'

        # When: Uploading an asset with a dangerous filename
        service = AWSS3Service()
        asset = await service.upload_asset(
            company_id=company.id,
            uploaded_by_id=user.id,
            parent_id=character.id,
            parent_fk_field="character_id",
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

    async def test_delete_object_from_s3_success(self, mocker: MockerFixture) -> None:
        """Verify _delete_object_from_s3 succeeds when S3 returns DeleteMarker True."""
        # Given: A mocked S3 client that returns DeleteMarker True
        mock_s3_client = mocker.MagicMock()
        mock_s3_client.get_bucket_location.return_value = {"LocationConstraint": "us-east-1"}
        mock_s3_client.delete_object.return_value = {"DeleteMarker": True}
        mocker.patch("vapi.domain.services.aws_service.boto3.client", return_value=mock_s3_client)

        # When: Deleting an object
        service = AWSS3Service()
        await service._delete_object_from_s3(key="test-key")

        # Then: delete_object was called with correct parameters
        mock_s3_client.delete_object.assert_called_once_with(
            Bucket=settings.aws.s3_bucket_name, Key="test-key"
        )

    async def test_delete_object_from_s3_raises_on_client_error(
        self, mocker: MockerFixture
    ) -> None:
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
            await service._delete_object_from_s3(key="test-key")


class TestDeleteAsset:
    """Test the delete_asset method."""

    async def test_delete_asset(
        self,
        s3asset_factory: Callable,
        company_factory: Callable,
        user_factory: Callable,
        mocker: MockerFixture,
    ) -> None:
        """Verify delete_asset removes asset from S3 and deletes the DB record."""
        # Given: An S3 asset
        company = await company_factory()
        user = await user_factory(company=company)
        asset = await s3asset_factory(company=company, uploaded_by=user)

        # Patch the S3 deletion
        mocker.patch.object(AWSS3Service, "_delete_object_from_s3")

        # When: Deleting the asset
        service = AWSS3Service()
        await service.delete_asset(asset)

        # Then: Asset is deleted from the database
        assert await S3Asset.filter(id=asset.id).first() is None

    async def test_delete_asset_raises_on_s3_error(
        self,
        s3asset_factory: Callable,
        company_factory: Callable,
        user_factory: Callable,
        mocker: MockerFixture,
    ) -> None:
        """Verify delete_asset raises AWSS3Error when S3 deletion fails."""
        # Given: An S3 asset
        company = await company_factory()
        user = await user_factory(company=company)
        asset = await s3asset_factory(company=company, uploaded_by=user)

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
