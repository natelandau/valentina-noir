"""Tests for the backup_database SAQ task."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from vapi.config.base import settings
from vapi.lib.exceptions import AWSS3Error
from vapi.lib.scheduled_tasks import backup_database

if TYPE_CHECKING:
    from collections.abc import Iterator
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


class TestBackupDatabaseGuards:
    """Tests for backup_database early-return guards."""

    async def test_returns_early_when_disabled(self, mocker: MockerFixture) -> None:
        """Verify backup_database returns immediately when backups are disabled."""
        # Given backups are disabled
        original = settings.backup.enabled
        settings.backup.enabled = False

        mock_subprocess = mocker.patch("vapi.lib.scheduled_tasks.asyncio.create_subprocess_exec")

        # When running the task
        await backup_database({})

        # Then pg_dump was never called
        mock_subprocess.assert_not_called()

        # Cleanup
        settings.backup.enabled = original

    async def test_returns_early_when_aws_not_configured(self, mocker: MockerFixture) -> None:
        """Verify backup_database returns when AWS credentials are missing."""
        # Given backups are enabled but AWS is not configured
        original_enabled = settings.backup.enabled
        original_key = settings.aws.access_key_id
        settings.backup.enabled = True
        settings.aws.access_key_id = None

        mock_subprocess = mocker.patch("vapi.lib.scheduled_tasks.asyncio.create_subprocess_exec")

        # When running the task
        await backup_database({})

        # Then pg_dump was never called
        mock_subprocess.assert_not_called()

        # Cleanup
        settings.backup.enabled = original_enabled
        settings.aws.access_key_id = original_key

    async def test_returns_early_on_pgdump_failure(self, mocker: MockerFixture) -> None:
        """Verify backup_database does not upload when pg_dump fails."""
        # Given backups are enabled and AWS is configured
        original_enabled = settings.backup.enabled
        original_key = settings.aws.access_key_id
        original_secret = settings.aws.secret_access_key
        original_bucket = settings.aws.s3_bucket_name
        settings.backup.enabled = True
        settings.aws.access_key_id = "test-key"
        settings.aws.secret_access_key = "test-secret"  # noqa: S105
        settings.aws.s3_bucket_name = "test-bucket"

        # Given pg_dump fails with non-zero return code
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"pg_dump: error: connection refused")
        mock_process.returncode = 1
        mocker.patch(
            "vapi.lib.scheduled_tasks.asyncio.create_subprocess_exec",
            return_value=mock_process,
        )
        mock_aws = mocker.patch("vapi.lib.scheduled_tasks.AWSS3Service")

        # When running the task
        await backup_database({})

        # Then upload_file was never called (pg_dump failed first)
        mock_aws.return_value.upload_file.assert_not_called()

        # Cleanup
        settings.backup.enabled = original_enabled
        settings.aws.access_key_id = original_key
        settings.aws.secret_access_key = original_secret
        settings.aws.s3_bucket_name = original_bucket


@pytest.fixture
def configured_backup() -> Iterator[None]:
    """Enable backups with AWS credentials and zero retention, restoring settings afterward."""
    backup = settings.backup
    aws = settings.aws
    originals = {
        "enabled": backup.enabled,
        "retain_daily": backup.retain_daily,
        "retain_weekly": backup.retain_weekly,
        "retain_monthly": backup.retain_monthly,
        "retain_yearly": backup.retain_yearly,
        "access_key_id": aws.access_key_id,
        "secret_access_key": aws.secret_access_key,
        "s3_bucket_name": aws.s3_bucket_name,
    }
    backup.enabled = True
    # Zero retention so any listed backup is a deletion candidate, making pruning deterministic
    backup.retain_daily = backup.retain_weekly = backup.retain_monthly = backup.retain_yearly = 0
    aws.access_key_id = "test-key"
    aws.secret_access_key = "test-secret"  # noqa: S105
    aws.s3_bucket_name = "test-bucket"
    yield
    backup.enabled = originals["enabled"]
    backup.retain_daily = originals["retain_daily"]
    backup.retain_weekly = originals["retain_weekly"]
    backup.retain_monthly = originals["retain_monthly"]
    backup.retain_yearly = originals["retain_yearly"]
    aws.access_key_id = originals["access_key_id"]
    aws.secret_access_key = originals["secret_access_key"]
    aws.s3_bucket_name = originals["s3_bucket_name"]


def _patch_pgdump_success(mocker: MockerFixture) -> None:
    """Patch pg_dump to complete successfully with a zero return code."""
    process = AsyncMock()
    process.communicate.return_value = (b"", b"")
    process.returncode = 0
    mocker.patch(
        "vapi.lib.scheduled_tasks.asyncio.create_subprocess_exec",
        return_value=process,
    )


def _patch_aws_service(
    mocker: MockerFixture,
    *,
    list_keys: list[str] | None = None,
    upload_side_effect: Exception | None = None,
    list_side_effect: Exception | None = None,
    delete_side_effect: object = None,
) -> MagicMock:
    """Patch AWSS3Service with async upload/list/delete methods, returning the instance mock."""
    service = mocker.MagicMock()
    service.upload_file = AsyncMock(side_effect=upload_side_effect)
    service.list_keys = AsyncMock(return_value=list_keys or [], side_effect=list_side_effect)
    service.delete_key = AsyncMock(side_effect=delete_side_effect)
    mocker.patch("vapi.lib.scheduled_tasks.AWSS3Service", return_value=service)
    return service


class TestBackupDatabaseFlow:
    """Tests for the backup_database upload, list, and prune flow."""

    async def test_success_uploads_and_prunes(
        self, configured_backup: None, mocker: MockerFixture
    ) -> None:
        """Verify a successful backup uploads the dump and deletes expired backups."""
        # Given pg_dump succeeds and S3 lists two expired backups
        _patch_pgdump_success(mocker)
        service = _patch_aws_service(
            mocker,
            list_keys=["db_backups/2020-01-01.dump", "db_backups/2020-01-02.dump"],
        )

        # When running the task
        await backup_database({})

        # Then the dump is uploaded and both expired backups are deleted
        service.upload_file.assert_awaited_once()
        service.list_keys.assert_awaited_once()
        assert service.delete_key.await_count == 2

    async def test_upload_failure_skips_pruning(
        self, configured_backup: None, mocker: MockerFixture
    ) -> None:
        """Verify a failed S3 upload aborts before listing or pruning backups."""
        # Given pg_dump succeeds but the S3 upload fails
        _patch_pgdump_success(mocker)
        service = _patch_aws_service(mocker, upload_side_effect=AWSS3Error(detail="upload failed"))

        # When running the task
        await backup_database({})

        # Then pruning never starts
        service.list_keys.assert_not_called()
        service.delete_key.assert_not_called()

    async def test_list_failure_skips_deletion(
        self, configured_backup: None, mocker: MockerFixture
    ) -> None:
        """Verify a failed backup listing aborts before any deletion."""
        # Given pg_dump and upload succeed but listing backups fails
        _patch_pgdump_success(mocker)
        service = _patch_aws_service(mocker, list_side_effect=AWSS3Error(detail="list failed"))

        # When running the task
        await backup_database({})

        # Then no deletion is attempted
        service.delete_key.assert_not_called()

    async def test_delete_failure_is_isolated(
        self, configured_backup: None, mocker: MockerFixture
    ) -> None:
        """Verify a failure deleting one expired backup does not abort the others."""
        # Given two expired backups where the second deletion fails
        _patch_pgdump_success(mocker)
        service = _patch_aws_service(
            mocker,
            list_keys=["db_backups/2020-01-01.dump", "db_backups/2020-01-02.dump"],
            delete_side_effect=[None, AWSS3Error(detail="delete failed")],
        )

        # When running the task / Then it completes without raising
        await backup_database({})

        # Then both deletions were attempted
        assert service.delete_key.await_count == 2
