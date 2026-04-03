"""S3 asset download and cleanup for migration."""

import logging
from pathlib import Path

import boto3
from beanie import PydanticObjectId
from botocore.config import Config as BotoConfig
from vapi.db.models import S3Asset

from vapi.config import settings

from .config import get_old_settings

logger = logging.getLogger("migrate")

S3_ASSETS_LOG = Path("scripts/migrate/s3_assets.log")


class S3Migrator:
    """Download S3 objects from old bucket and clean up migrated company prefixes.

    Tracks migrated company IDs in a log file so subsequent runs can clean up
    all S3 objects and database records for those companies before re-migrating.
    """

    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self._company_ids: set[PydanticObjectId] = set()

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
        self._prefix = (
            settings.aws.cloudfront_origin_path.rstrip("/") + "/"
            if settings.aws.cloudfront_origin_path
            else ""
        )

    def download_object(self, old_key: str) -> bytes:
        """Download an object from the old S3 bucket and return its bytes.

        Args:
            old_key: The key in the old bucket.

        Returns:
            The raw bytes of the object.
        """
        response = self._old_client.get_object(Bucket=self._old_bucket, Key=old_key)
        return response["Body"].read()

    @staticmethod
    def _parse_company_ids(lines: list[str]) -> list[PydanticObjectId]:
        """Parse company IDs from log file lines, skipping invalid entries.

        Handles old-format logs that contain individual S3 keys instead of ObjectIds.

        Args:
            lines: Raw lines from the log file.

        Returns:
            Valid PydanticObjectId values parsed from the lines.
        """
        company_ids: list[PydanticObjectId] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                company_ids.append(PydanticObjectId(stripped))
            except Exception:  # noqa: BLE001
                logger.warning("Skipping invalid company ID in log: %s", stripped)
        return company_ids

    async def _cleanup_company(self, company_id: PydanticObjectId) -> None:
        """Delete all S3 objects and database records for a single company.

        Args:
            company_id: The company whose assets should be deleted.
        """
        prefix = f"{self._prefix}{company_id}/"

        # List and delete all S3 objects under the company prefix (paginated)
        paginator = self._new_client.get_paginator("list_objects_v2")
        deleted_total = 0
        for page in paginator.paginate(Bucket=self._new_bucket, Prefix=prefix):
            objects = page.get("Contents", [])
            if objects:
                delete_keys = [{"Key": obj["Key"]} for obj in objects]
                self._new_client.delete_objects(
                    Bucket=self._new_bucket,
                    Delete={"Objects": delete_keys},
                )
                deleted_total += len(delete_keys)
        if deleted_total:
            logger.info("Deleted %d S3 objects under %s", deleted_total, prefix)

        # Delete S3Asset database records for this company
        deleted_count = await S3Asset.find(S3Asset.company_id == company_id).delete()
        logger.info("Deleted %s S3Asset records for company %s", deleted_count, company_id)

    async def cleanup_previous_run(self) -> None:
        """Delete S3 objects and database records from a previous migration run.

        Read company IDs from the log file. For each company, list and delete all
        S3 objects under its prefix in the new bucket, then delete all S3Asset
        documents for that company.
        """
        if not S3_ASSETS_LOG.exists():  # noqa: ASYNC240
            return

        lines = S3_ASSETS_LOG.read_text().strip().splitlines()  # noqa: ASYNC240
        if not lines:
            return

        company_ids = self._parse_company_ids(lines)
        if not company_ids:
            logger.info("No valid company IDs found in log file, skipping cleanup")
            return

        logger.info("Cleaning up %d companies from previous run", len(company_ids))

        for company_id in company_ids:
            if self.dry_run:
                prefix = f"{self._prefix}{company_id}/"
                logger.info(
                    "[DRY RUN] Would delete all objects under s3://%s/%s", self._new_bucket, prefix
                )
                logger.info("[DRY RUN] Would delete S3Asset records for company %s", company_id)
                continue

            await self._cleanup_company(company_id)

        # Clear the log file after cleanup to prevent re-deleting on crash before save_log
        if not self.dry_run:
            S3_ASSETS_LOG.write_text("")  # noqa: ASYNC240

    def record_company(self, company_id: PydanticObjectId) -> None:
        """Record a migrated company ID for the log file.

        Args:
            company_id: The new company's PydanticObjectId.
        """
        self._company_ids.add(company_id)

    def save_log(self) -> None:
        """Write migrated company IDs to the log file, overwriting any previous log."""
        content = (
            "\n".join(str(cid) for cid in self._company_ids) + "\n" if self._company_ids else ""
        )
        S3_ASSETS_LOG.write_text(content)
        logger.info("Wrote %d company IDs to %s", len(self._company_ids), S3_ASSETS_LOG)
