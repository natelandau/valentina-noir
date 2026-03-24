"""S3 asset copying and cleanup for migration."""

import logging
import mimetypes
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from vapi.config import settings

from .config import get_old_settings

logger = logging.getLogger("migrate")

S3_ASSETS_LOG = Path("scripts/migrate/s3_assets.log")


class S3Migrator:
    """Copy S3 objects from old bucket to new bucket with cleanup support.

    Tracks all copied keys in a log file so subsequent runs can clean up
    orphaned objects before re-migrating.
    """

    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self._copied_keys: list[str] = []

        old_settings = get_old_settings()
        self._old_client = boto3.client(
            "s3",
            aws_access_key_id=old_settings.aws_access_key_id,
            aws_secret_access_key=old_settings.aws_secret_access_key,
            config=BotoConfig(retries={"max_attempts": 3, "mode": "standard"}),
        )
        self._new_client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws.access_key_id,
            aws_secret_access_key=settings.aws.secret_access_key,
            config=BotoConfig(retries={"max_attempts": 3, "mode": "standard"}),
        )

        self._old_bucket = old_settings.s3_bucket_name
        self._new_bucket = settings.aws.s3_bucket_name

    def cleanup_previous_run(self) -> None:
        """Delete S3 objects from a previous migration run using the log file.

        Only deletes from the destination bucket. Never touches the source bucket.
        """
        if not S3_ASSETS_LOG.exists():
            return

        keys = S3_ASSETS_LOG.read_text().strip().splitlines()
        if not keys:
            return

        logger.info("Cleaning up %d S3 objects from previous run", len(keys))
        for key in keys:
            if self.dry_run:
                logger.info("[DRY RUN] Would delete s3://%s/%s", self._new_bucket, key)
                continue
            try:
                self._new_client.head_object(Bucket=self._new_bucket, Key=key)
                self._new_client.delete_object(Bucket=self._new_bucket, Key=key)
                logger.debug("Deleted s3://%s/%s", self._new_bucket, key)
            except ClientError:
                logger.debug("Object not found, skipping: s3://%s/%s", self._new_bucket, key)

    def copy_object(self, old_key: str, new_key: str) -> None:
        """Copy a single S3 object from old bucket to new bucket.

        Args:
            old_key: The key in the old bucket.
            new_key: The key in the new bucket.
        """
        if self.dry_run:
            logger.info(
                "[DRY RUN] Would copy s3://%s/%s -> s3://%s/%s",
                self._old_bucket,
                old_key,
                self._new_bucket,
                new_key,
            )
            self._copied_keys.append(new_key)
            return

        try:
            response = self._old_client.get_object(Bucket=self._old_bucket, Key=old_key)
            self._new_client.put_object(
                Bucket=self._new_bucket,
                Key=new_key,
                Body=response["Body"].read(),
                ContentType=response.get("ContentType", "application/octet-stream"),
            )
            self._copied_keys.append(new_key)
            logger.info(
                "Copied s3://%s/%s -> s3://%s/%s",
                self._old_bucket,
                old_key,
                self._new_bucket,
                new_key,
            )
        except ClientError:
            logger.exception("Failed to copy s3://%s/%s", self._old_bucket, old_key)

    def save_log(self) -> None:
        """Write all copied S3 keys to the log file, overwriting any previous log."""
        S3_ASSETS_LOG.write_text("\n".join(self._copied_keys) + "\n" if self._copied_keys else "")
        logger.info("Wrote %d S3 keys to %s", len(self._copied_keys), S3_ASSETS_LOG)

    @staticmethod
    def derive_mime_type(key: str) -> str:
        """Derive MIME type from a file extension in an S3 key.

        Args:
            key: The S3 key.

        Returns:
            The MIME type string.
        """
        mime_type, _ = mimetypes.guess_type(key)
        return mime_type or "application/octet-stream"

    def build_public_url(self, key: str) -> str:
        """Build the public URL for an object in the new bucket.

        Uses CloudFront URL if configured, otherwise falls back to direct S3 URL.

        Args:
            key: The S3 key in the new bucket.

        Returns:
            The public URL string.
        """
        if settings.aws.cloudfront_url:
            return f"{settings.aws.cloudfront_url}/{key}"
        return f"https://{self._new_bucket}.s3.amazonaws.com/{key}"
