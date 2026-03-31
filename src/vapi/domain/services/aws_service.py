"""AWS service."""

from pathlib import Path
from uuid import uuid4

import boto3
from beanie import PydanticObjectId
from botocore.config import Config
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
from vapi.db.models.base import BaseDocument
from vapi.lib.exceptions import AWSS3Error, MissingConfigurationError
from vapi.utils.assets import (
    add_asset_to_parent,
    determine_asset_type,
    determine_parent_type,
    remove_asset_from_parent,
    sanitize_filename,
)
from vapi.utils.time import time_now

__all__ = ("AWSS3Service",)


class AWSS3Service:
    """Service for interacting with AWS."""

    def __init__(self) -> None:
        """Initialize the AWS Service class with credentials from settings."""
        self.aws_access_key_id = settings.aws.access_key_id
        self.aws_secret_access_key = settings.aws.secret_access_key
        self.bucket_name = settings.aws.s3_bucket_name
        self.prefix = (
            settings.aws.cloudfront_origin_path.rstrip("/") + "/"
            if settings.aws.cloudfront_origin_path
            else ""
        )

        if not self.aws_access_key_id or not self.aws_secret_access_key or not self.bucket_name:
            msg = "AWS"
            raise MissingConfigurationError(msg)

        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            config=Config(retries={"max_attempts": 10, "mode": "standard"}),
        )

    def _generate_aws_key(
        self,
        company_id: PydanticObjectId,
        parent_type: AssetParentType,
        parent_object_id: PydanticObjectId,
        extension: str,
        asset_type: AssetType,
    ) -> str:
        """Build the full S3 key from company, parent, and asset metadata.

        Args:
            company_id: ID of the company.
            parent_type: Type of the parent object.
            parent_object_id: ID of the parent object.
            extension: File extension.
            asset_type: Type of the asset.

        Returns:
            str: The full key for the object in the S3 bucket.
        """
        prefix = (
            f"{self.prefix}{company_id}/{parent_type.value}/{parent_object_id}/{asset_type.value}"
        )
        date = time_now().strftime("%Y%m%dT%H%M%S")
        filename = f"{date}{uuid4().hex}.{extension}"
        return f"{prefix}/{filename}"

    def _delete_object_from_s3(self, key: str) -> None:
        """Delete an object from the S3 bucket.

        Args:
            key: Key of the object to delete.

        Raises:
            AWSS3Error: If the deletion fails.
        """
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
        except ClientError as e:
            msg = "Failed to delete object from AWS S3"
            raise AWSS3Error(detail=msg) from e

    def _generate_public_url(self, key: str) -> str:
        """Get the public URL for any object in the S3 bucket by its key.

        Args:
            key: Key of the object in the S3 bucket.

        Returns:
            Public URL for the object.
        """
        key_for_url = key.replace(self.prefix, "") if settings.aws.cloudfront_origin_path else key

        return f"{settings.aws.cloudfront_url.rstrip('/')}/{key_for_url}"

    def _get_cache_control(self, asset_type: AssetType) -> str:
        """Determine appropriate cache control header based on asset type.

        Args:
            asset_type: Type of the asset.

        Returns:
            Cache-Control header value.
        """
        if asset_type in {AssetType.IMAGE, AssetType.AUDIO, AssetType.VIDEO}:
            return AWS_ONE_YEAR_CACHE_HEADER

        if asset_type is AssetType.DOCUMENT:
            return AWS_ONE_DAY_CACHE_HEADER

        return AWS_ONE_HOUR_CACHE_HEADER

    async def _upload_to_s3(self, asset: S3Asset, data: bytes) -> None:
        """Upload data to the S3 bucket.

        Args:
            asset: S3Asset document to upload to the S3 bucket.
            data: Data to upload to the S3 bucket.
        """
        cache_control = self._get_cache_control(asset.asset_type)
        try:
            self.s3.put_object(
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
        """Delete an asset from S3, remove it from its parent, and delete the database record.

        S3 delete_object is idempotent, so no existence check is needed.

        Args:
            asset: S3Asset document to delete.

        Raises:
            AWSS3Error: If the S3 deletion fails.
        """
        self._delete_object_from_s3(key=asset.s3_key)
        await remove_asset_from_parent(asset=asset)
        await asset.delete()

    async def upload_asset(
        self,
        *,
        parent: BaseDocument | None = None,
        company_id: PydanticObjectId,
        upload_user_id: PydanticObjectId,
        data: bytes,
        filename: str,
        mime_type: str,
    ) -> S3Asset:
        """Upload an asset and attach it to a parent document.

        Args:
            parent: Parent document to attach the asset to (must have asset_ids attribute).
            company_id: ID of the company
            upload_user_id: ID of the user uploading the asset
            data: Binary file data
            filename: Original filename
            mime_type: MIME type of the file

        Returns:
            The created S3Asset document
        """
        asset_type = determine_asset_type(mime_type)
        parent_type = determine_parent_type(parent=parent)
        extension = Path(filename).suffix.lstrip(".")
        filename = sanitize_filename(filename)

        s3_key = self._generate_aws_key(
            company_id=company_id,
            parent_type=parent_type,
            parent_object_id=parent.id,
            extension=extension,
            asset_type=asset_type,
        )

        asset = S3Asset(
            asset_type=asset_type,
            mime_type=mime_type,
            parent_type=parent_type,
            parent_id=parent.id,
            s3_key=s3_key,
            s3_bucket=settings.aws.s3_bucket_name,
            public_url=self._generate_public_url(s3_key),
            uploaded_by=upload_user_id,
            company_id=company_id,
            original_filename=filename,
        )
        await asset.insert()
        await self._upload_to_s3(asset=asset, data=data)

        await add_asset_to_parent(asset=asset)

        return asset
