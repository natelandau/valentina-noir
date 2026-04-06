"""Tests for the backup_database SAQ task."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from vapi.config.base import settings
from vapi.lib.scheduled_tasks import backup_database

if TYPE_CHECKING:
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
