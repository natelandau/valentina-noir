"""AWS service."""

import logging
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
    AssetType,
)
from vapi.db.models import Campaign, CampaignBook, CampaignChapter, Character, S3Asset, User
from vapi.lib.exceptions import AWSS3Error, MissingConfigurationError
from vapi.utils.assets import determine_asset_type, sanitize_filename
from vapi.utils.time import time_now

logger = logging.getLogger("vapi")


__all__ = ("AWSS3Service",)


class AWSS3Service:
    """Service for interacting with AWS."""

    def __init__(self) -> None:
        """Initialize the AWS Service class with credentials.

        Args:
            aws_access_key_id (str): AWS access key ID.
            aws_secret_access_key (str): AWS secret access key.
            bucket_name (str): Name of the S3 bucket to use.
        """
        self.aws_access_key_id = settings.aws.access_key_id
        self.aws_secret_access_key = settings.aws.secret_access_key
        self.bucket_name = settings.aws.s3_bucket_name

        if not self.aws_access_key_id or not self.aws_secret_access_key or not self.bucket_name:
            msg = "AWS"
            raise MissingConfigurationError(msg)

        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            config=Config(retries={"max_attempts": 10, "mode": "standard"}),
        )
        self.bucket = self.bucket_name
        self.location = self.s3.get_bucket_location(Bucket=self.bucket)  # Ex. us-east-1

    def _generate_aws_key(
        self,
        company_id: PydanticObjectId,
        parent_type: str,
        parent_object_id: PydanticObjectId,
        extension: str,
        asset_type: AssetType,
    ) -> str:
        """Build the full key for an object in the S3 bucket.

        Args:
            company_id (PydanticObjectId): ID of the company.
            parent_type (str): Type of the parent object.
            parent_object_id (PydanticObjectId): ID of the parent object.
            extension (str): Extension of the file.
            asset_type (AssetType): Type of the asset.

        Returns:
            str: The full key for the object in the S3 bucket.
        """

        def _generate_object_filename(extension: str) -> str:
            """Generate a filename for an object in the S3 bucket.

            The filename is generated based on the date and time of the upload and a unique ID. Append this to the key prefix to get the full key for the full object in the S3 bucket.

            Args:
                extension (str): Extension of the file.

            Returns:
                str: The generated filename.
            """
            date = time_now().strftime("%Y%m%dT%H%M%S")
            unique_id = uuid4().hex
            return f"{date}{unique_id}.{extension}"

        def _build_key_prefix(
            company_id: PydanticObjectId,
            parent_type: str,
            parent_object_id: PydanticObjectId,
            asset_type: AssetType,
        ) -> str:
            """Generate a key prefix for an object to be uploaded to Amazon S3.

            The key prefix is generated based on the area (guild, author, character, campaign, etc.)
            that the object belongs to. Some areas may require additional information like a character_id
            or a campaign_id.

            Args:
                company_id (PydanticObjectId): ID of the company.
                parent_type (str): Type of the parent object.
                parent_object_id (PydanticObjectId): ID of the parent object.
                asset_type (AssetType): Type of the asset.

            Returns:
                str: The generated key prefix.
            """
            prefix = (
                settings.aws.cloudfront_origin_path.rstrip("/") + "/"
                if settings.aws.cloudfront_origin_path
                else ""
            )
            return f"{prefix}{company_id}/{parent_type}/{parent_object_id}/{asset_type.value}"

        key_prefix = _build_key_prefix(
            company_id=company_id,
            parent_type=parent_type,
            parent_object_id=parent_object_id,
            asset_type=asset_type,
        )
        generated_filename = _generate_object_filename(extension=extension)
        return f"{key_prefix}/{generated_filename}"

    def _delete_object_from_s3(self, key: str) -> None:
        """Delete an object from the S3 bucket.

        Attempt to delete the object from the S3 bucket using the provided key.
        If the deletion fails, log the error and return False.

        Args:
            key (str): Key of the object to delete from the S3 bucket.

        Returns:
            bool: True if the deletion is successful, False otherwise.

        Raises:
            AWSS3Error: If the deletion fails.
        """
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            msg = "Failed to delete object from AWS S3"
            raise AWSS3Error(detail=msg) from e

    def _get_cache_control(self, mime_type: str) -> str:
        """Determine appropriate cache control header based on MIME type.

        Args:
            mime_type: MIME type of the file.

        Returns:
            Cache-Control header value.
        """
        # Images can be cached aggressively (1 year)
        if mime_type.startswith("image/"):
            return AWS_ONE_YEAR_CACHE_HEADER

        # Audio/video can also be cached long-term
        if mime_type.startswith(("audio/", "video/")):
            return AWS_ONE_YEAR_CACHE_HEADER

        # Documents might change, cache for 1 day
        if any(doc_type in mime_type.lower() for doc_type in ["pdf", "document", "word", "sheet"]):
            return AWS_ONE_DAY_CACHE_HEADER

        # Default: cache for 1 hour
        return AWS_ONE_HOUR_CACHE_HEADER

    async def _upload_to_s3(self, key: str, data: bytes, mime_type: str, filename: str) -> None:
        """Upload data to the S3 bucket.

        Args:
            key: Key of the object to upload to the S3 bucket.
            data: Data to upload to the S3 bucket.
            mime_type: MIME type of the data.
            filename: Original filename.
        """
        cache_control = self._get_cache_control(mime_type)
        try:
            self.s3.put_object(
                Key=key,
                Bucket=self.bucket,
                Body=data,
                ContentType=mime_type,
                CacheControl=cache_control,
                ContentDisposition=f'inline; filename="{filename}"',
                Metadata={
                    "uploaded-via": settings.slug,
                    "original-filename": filename,
                },
            )
        except (ClientError, FileNotFoundError) as e:
            msg = "Failed to upload file to AWS S3"
            raise AWSS3Error(detail=msg) from e

    async def delete_asset(
        self,
        asset: S3Asset,
        parent: Character | User | Campaign | CampaignBook | CampaignChapter,
    ) -> bool:
        """Delete an asset from the S3 bucket.

        Args:
            asset: S3Asset document to delete from the S3 bucket.
            parent: Parent document to remove the asset from (must have asset_ids attribute).

        Returns:
            bool: True if the deletion is successful, False otherwise.

        Raises:
            AWSS3Error: If the deletion fails.
            AttributeError: If the parent document does not have the asset_ids attribute.
        """
        try:
            self._delete_object_from_s3(key=asset.s3_key)
        except AWSS3Error as e:
            msg = f"Failed to delete asset {asset.s3_key} from AWS S3"
            raise AWSS3Error(detail=msg) from e

        asset.is_archived = True
        await asset.save()

        if not hasattr(parent, "asset_ids"):
            msg = f"{parent.__class__.__name__} does not have 'asset_ids' attribute"
            raise AttributeError(msg)

        if parent.asset_ids is None:
            parent.asset_ids = []

        parent.asset_ids.remove(asset.id)
        await parent.save()

        return True

    def get_url(self, key: str) -> str:
        """Get the public URL for any object in the S3 bucket by its key.

        Args:
            key: Key of the object in the S3 bucket.

        Returns:
            Public URL for the object.
        """
        prefix = settings.aws.cloudfront_origin_path.rstrip("/") + "/"
        key_for_url = key.replace(prefix, "")

        return f"{settings.aws.cloudfront_url.rstrip('/')}/{key_for_url}"

    async def upload_asset(
        self,
        *,
        parent: Character | User | Campaign | CampaignBook | CampaignChapter,
        company_id: PydanticObjectId,
        upload_user_id: PydanticObjectId,
        data: bytes,
        filename: str,
        mime_type: str,
    ) -> S3Asset:
        """Upload an asset and attach it to a parent document.

        Asset type is automatically determined from the MIME type.

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
        extension = Path(filename).suffix.lstrip(".")
        filename = sanitize_filename(filename)
        parent_type = parent.__class__.__name__.lower()

        s3_key = self._generate_aws_key(
            company_id=company_id,
            parent_type=parent_type,
            parent_object_id=parent.id,
            extension=extension,
            asset_type=asset_type,
        )

        await self._upload_to_s3(key=s3_key, data=data, mime_type=mime_type, filename=filename)

        asset = S3Asset(
            asset_type=asset_type,
            mime_type=mime_type,
            parent_type=parent_type,
            parent_id=parent.id,
            s3_key=s3_key,
            s3_bucket=settings.aws.s3_bucket_name,
            public_url=self.get_url(s3_key),
            uploaded_by=upload_user_id,
            company_id=company_id,
            original_filename=filename,
        )
        await asset.insert()

        if not hasattr(parent, "asset_ids"):
            msg = f"{parent.__class__.__name__} does not have 'asset_ids' attribute"
            raise AttributeError(msg)

        if parent.asset_ids is None:
            parent.asset_ids = []

        parent.asset_ids.append(asset.id)
        await parent.save()

        return asset
