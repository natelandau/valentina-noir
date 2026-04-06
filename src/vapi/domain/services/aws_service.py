"""AWS service."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from vapi.config.base import settings
from vapi.constants import (
    AWS_ONE_DAY_CACHE_HEADER,
    AWS_ONE_HOUR_CACHE_HEADER,
    AWS_ONE_YEAR_CACHE_HEADER,
    AssetType,
)
from vapi.db.sql_models.aws import S3Asset
from vapi.lib.exceptions import AWSS3Error, MissingConfigurationError
from vapi.utils.assets import determine_asset_type, sanitize_filename
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ("AWSS3Service",)


class AWSS3Service:
    """Service for interacting with AWS."""

    def __init__(self) -> None:
        """Initialize the AWS Service class with credentials from settings."""
        aws_access_key_id = settings.aws.access_key_id
        aws_secret_access_key = settings.aws.secret_access_key
        self.bucket_name = settings.aws.s3_bucket_name
        self.prefix = (
            settings.aws.cloudfront_origin_path.rstrip("/") + "/"
            if settings.aws.cloudfront_origin_path
            else ""
        )

        if not aws_access_key_id or not aws_secret_access_key or not self.bucket_name:
            msg = "AWS"
            raise MissingConfigurationError(msg)

        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            config=Config(retries={"max_attempts": 10, "mode": "standard"}),
        )

    def _generate_aws_key(
        self,
        company_id: UUID,
        parent_id: UUID,
        extension: str,
        asset_type: AssetType,
    ) -> str:
        """Build the full S3 key from company, parent, and asset metadata."""
        prefix = f"{self.prefix}{company_id}/{parent_id}/{asset_type.value}"
        date = time_now().strftime("%Y%m%dT%H%M%S")
        filename = f"{date}{uuid4().hex}.{extension}"
        return f"{prefix}/{filename}"

    def _generate_public_url(self, key: str) -> str:
        """Get the public URL for any object in the S3 bucket by its key."""
        key_for_url = key.replace(self.prefix, "") if settings.aws.cloudfront_origin_path else key
        return f"{settings.aws.cloudfront_url.rstrip('/')}/{key_for_url}"

    def _get_cache_control(self, asset_type: AssetType) -> str:
        """Determine appropriate cache control header based on asset type."""
        if asset_type in {AssetType.IMAGE, AssetType.AUDIO, AssetType.VIDEO}:
            return AWS_ONE_YEAR_CACHE_HEADER
        if asset_type is AssetType.DOCUMENT:
            return AWS_ONE_DAY_CACHE_HEADER
        return AWS_ONE_HOUR_CACHE_HEADER

    async def upload_file(self, key: str, file_path: Path, content_type: str) -> None:
        """Stream a file from disk to the S3 bucket under the given key.

        Use this for large files (e.g., database dumps) so the file is uploaded
        in chunks via boto3's multipart upload rather than loaded entirely into
        memory.

        Args:
            key: The full S3 object key (e.g., "db_backups/2026-04-06.dump").
            file_path: Path to the file to upload.
            content_type: MIME type of the file.
        """
        try:
            await asyncio.to_thread(
                self.s3.upload_file,
                str(file_path),
                self.bucket_name,
                key,
                ExtraArgs={"ContentType": content_type},
            )
        except ClientError as e:
            msg = "Failed to upload file to AWS S3"
            raise AWSS3Error(detail=msg) from e

    async def list_keys(self, prefix: str) -> list[str]:
        """List all object keys under a prefix.

        Args:
            prefix: The S3 key prefix to list (e.g., "db_backups/").

        Returns:
            A list of S3 object keys matching the prefix.
        """
        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            pages = await asyncio.to_thread(
                lambda: list(paginator.paginate(Bucket=self.bucket_name, Prefix=prefix))
            )
        except ClientError as e:
            msg = "Failed to list objects from AWS S3"
            raise AWSS3Error(detail=msg) from e
        else:
            return [obj["Key"] for page in pages for obj in page.get("Contents", [])]

    async def delete_key(self, key: str) -> None:
        """Delete a single object from the S3 bucket by key.

        Args:
            key: The full S3 object key to delete.
        """
        try:
            await asyncio.to_thread(self.s3.delete_object, Bucket=self.bucket_name, Key=key)
        except ClientError as e:
            msg = "Failed to delete object from AWS S3"
            raise AWSS3Error(detail=msg) from e

    async def _upload_to_s3(self, asset: S3Asset, data: bytes) -> None:
        """Upload data to the S3 bucket."""
        cache_control = self._get_cache_control(asset.asset_type)
        try:
            await asyncio.to_thread(
                self.s3.put_object,
                Key=asset.s3_key,
                Bucket=self.bucket_name,
                Body=data,
                ContentType=asset.mime_type,
                CacheControl=cache_control,
                ContentDisposition=f'inline; filename="{asset.original_filename}"',
                Metadata={
                    "uploaded-via": settings.slug,
                    "original-filename": asset.original_filename,
                },
            )
        except (ClientError, FileNotFoundError) as e:
            msg = "Failed to upload file to AWS S3"
            raise AWSS3Error(detail=msg) from e

    async def delete_asset(self, asset: S3Asset) -> None:
        """Delete an asset from S3 and the database."""
        await self.delete_key(key=asset.s3_key)
        await asset.delete()

    async def upload_asset(
        self,
        *,
        company_id: UUID,
        uploaded_by_id: UUID,
        parent_id: UUID,
        parent_fk_field: str,
        data: bytes,
        filename: str,
        mime_type: str,
    ) -> S3Asset:
        """Upload an asset and create the database record.

        Args:
            company_id: ID of the company.
            uploaded_by_id: ID of the user uploading the asset.
            parent_id: ID of the parent entity.
            parent_fk_field: FK field name on S3Asset (e.g., "character_id").
            data: Binary file data.
            filename: Original filename.
            mime_type: MIME type of the file.

        Returns:
            The created S3Asset record.
        """
        asset_type = determine_asset_type(mime_type)
        extension = Path(filename).suffix.lstrip(".")
        filename = sanitize_filename(filename)

        s3_key = self._generate_aws_key(
            company_id=company_id,
            parent_id=parent_id,
            extension=extension,
            asset_type=asset_type,
        )

        create_kwargs = {
            "asset_type": asset_type,
            "mime_type": mime_type,
            "s3_key": s3_key,
            "s3_bucket": settings.aws.s3_bucket_name,
            "public_url": self._generate_public_url(s3_key),
            "uploaded_by_id": uploaded_by_id,
            "company_id": company_id,
            "original_filename": filename,
            parent_fk_field: parent_id,
        }
        asset = await S3Asset.create(**create_kwargs)  # type: ignore[arg-type]

        try:
            await self._upload_to_s3(asset=asset, data=data)
        except AWSS3Error:
            await asset.delete()
            raise

        return asset
