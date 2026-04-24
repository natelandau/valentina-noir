"""Tests for DatabaseRestoreService."""

from __future__ import annotations

import asyncio
import os
from contextlib import nullcontext
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from vapi.config.base import settings
from vapi.lib.db_restore import DatabaseRestoreService, LocalFileSource, S3Source
from vapi.lib.exceptions import DatabaseRestoreError, MissingConfigurationError

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


def _mock_tempfile(mocker: MockerFixture, path: Path) -> None:
    """Patch NamedTemporaryFile to yield an object whose ``.name`` equals ``str(path)``."""
    mocker.patch(
        "vapi.lib.db_restore.NamedTemporaryFile",
        return_value=nullcontext(SimpleNamespace(name=str(path))),
    )


class TestResolveSource:
    """Tests for source resolution (S3 vs local file)."""

    async def test_local_file_source_returns_path_and_no_cleanup(
        self,
        tmp_path: Path,
    ) -> None:
        """Verify local file source returns the user's path and marks it not-for-cleanup."""
        # Given an existing local dump file
        dump = tmp_path / "local.dump"
        dump.write_bytes(b"not a real dump, just bytes")
        service = DatabaseRestoreService()

        # When resolving the source
        resolved_path, should_cleanup = await service.resolve_source(LocalFileSource(path=dump))

        # Then the path is returned and cleanup is disabled
        assert resolved_path == dump
        assert should_cleanup is False

    async def test_s3_source_picks_latest_when_no_key_given(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
    ) -> None:
        """Verify S3 source with key=None downloads the lexicographically-largest key."""
        # Given an AWSS3Service that lists three keys out of order
        mock_aws = mocker.MagicMock()
        mock_aws.list_keys = mocker.AsyncMock(
            return_value=[
                "db_backups/2026-04-10.dump",
                "db_backups/2026-04-15.dump",
                "db_backups/2026-04-12.dump",
            ]
        )
        mock_aws.download_file = mocker.AsyncMock()
        mocker.patch("vapi.lib.db_restore.AWSS3Service", return_value=mock_aws)

        # Given a tempfile target
        _mock_tempfile(mocker, tmp_path / "latest.dump")

        service = DatabaseRestoreService()

        # When resolving the source with no explicit key
        resolved_path, should_cleanup = await service.resolve_source(S3Source(key=None))

        # Then the latest key was downloaded
        mock_aws.list_keys.assert_awaited_once_with(prefix="db_backups/")
        mock_aws.download_file.assert_awaited_once()
        download_kwargs = mock_aws.download_file.await_args.kwargs
        assert download_kwargs["key"] == "db_backups/2026-04-15.dump"
        assert should_cleanup is True
        assert resolved_path == tmp_path / "latest.dump"

    async def test_s3_source_with_explicit_key_downloads_that_key(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
    ) -> None:
        """Verify S3 source with an explicit key downloads exactly that key."""
        # Given an AWSS3Service
        mock_aws = mocker.MagicMock()
        mock_aws.download_file = mocker.AsyncMock()
        mocker.patch("vapi.lib.db_restore.AWSS3Service", return_value=mock_aws)
        _mock_tempfile(mocker, tmp_path / "specific.dump")

        service = DatabaseRestoreService()

        # When resolving with an explicit key
        await service.resolve_source(S3Source(key="db_backups/2026-04-01.dump"))

        # Then list_keys was NOT called
        mock_aws.list_keys.assert_not_called()
        # And download_file was called with the given key
        mock_aws.download_file.assert_awaited_once()
        assert mock_aws.download_file.await_args.kwargs["key"] == "db_backups/2026-04-01.dump"

    async def test_s3_source_raises_when_prefix_is_empty(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Verify a DatabaseRestoreError is raised when db_backups/ is empty."""
        # Given an AWSS3Service with no backups
        mock_aws = mocker.MagicMock()
        mock_aws.list_keys = mocker.AsyncMock(return_value=[])
        mocker.patch("vapi.lib.db_restore.AWSS3Service", return_value=mock_aws)

        service = DatabaseRestoreService()

        # When resolving latest-key source against an empty prefix
        # Then DatabaseRestoreError is raised with a clear message
        with pytest.raises(DatabaseRestoreError, match="No backups found"):
            await service.resolve_source(S3Source(key=None))

    async def test_s3_source_surfaces_missing_config_as_restore_error(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Verify missing AWS creds produce a DatabaseRestoreError pointing at --file."""
        # Given AWSS3Service constructor raises MissingConfigurationError
        mocker.patch(
            "vapi.lib.db_restore.AWSS3Service",
            side_effect=MissingConfigurationError("AWS"),
        )

        service = DatabaseRestoreService()

        # When resolving an S3 source
        # Then a DatabaseRestoreError is raised with a --file hint
        with pytest.raises(DatabaseRestoreError, match="--file"):
            await service.resolve_source(S3Source(key=None))


class TestRun:
    """Tests for DatabaseRestoreService.run end-to-end orchestration."""

    async def test_run_with_local_file_does_not_delete_user_file(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
    ) -> None:
        """Verify restoring from --file never deletes the user-provided dump."""
        # Given an existing local dump file
        dump = tmp_path / "user.dump"
        dump.write_bytes(b"dump")

        # Given pg_restore succeeds and drop_and_recreate is stubbed
        mock_drop = mocker.patch("vapi.lib.db_restore.drop_and_recreate_database", new=AsyncMock())
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mocker.patch(
            "vapi.lib.db_restore.asyncio.create_subprocess_exec",
            return_value=mock_process,
        )

        service = DatabaseRestoreService()

        # When restoring
        await service.run(source=LocalFileSource(path=dump))

        # Then drop_and_recreate_database was called
        mock_drop.assert_awaited_once()
        # And the user's file is still on disk
        assert dump.exists()

    async def test_run_with_s3_source_deletes_temp_file_on_success(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
    ) -> None:
        """Verify a downloaded temp dump is deleted after a successful restore."""
        # Given an AWSS3Service that "downloads" into tmp
        dump = tmp_path / "download.dump"
        dump.write_bytes(b"dump")

        mock_aws = mocker.MagicMock()
        mock_aws.list_keys = AsyncMock(return_value=["db_backups/2026-04-15.dump"])
        mock_aws.download_file = AsyncMock()
        mocker.patch("vapi.lib.db_restore.AWSS3Service", return_value=mock_aws)
        _mock_tempfile(mocker, dump)

        mocker.patch("vapi.lib.db_restore.drop_and_recreate_database", new=AsyncMock())
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mocker.patch(
            "vapi.lib.db_restore.asyncio.create_subprocess_exec",
            return_value=mock_process,
        )

        service = DatabaseRestoreService()

        # When restoring from S3 latest
        await service.run(source=S3Source(key=None))

        # Then the temp dump was unlinked
        assert not dump.exists()

    async def test_run_deletes_temp_file_even_on_pg_restore_failure(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
    ) -> None:
        """Verify the temp dump is cleaned up even when pg_restore fails."""
        # Given a downloaded temp dump and a failing pg_restore
        dump = tmp_path / "download.dump"
        dump.write_bytes(b"dump")

        mock_aws = mocker.MagicMock()
        mock_aws.list_keys = AsyncMock(return_value=["db_backups/2026-04-15.dump"])
        mock_aws.download_file = AsyncMock()
        mocker.patch("vapi.lib.db_restore.AWSS3Service", return_value=mock_aws)
        _mock_tempfile(mocker, dump)

        mocker.patch("vapi.lib.db_restore.drop_and_recreate_database", new=AsyncMock())
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"pg_restore: error: broken")
        mock_process.returncode = 1
        mocker.patch(
            "vapi.lib.db_restore.asyncio.create_subprocess_exec",
            return_value=mock_process,
        )

        service = DatabaseRestoreService()

        # When restoring and pg_restore fails
        # Then DatabaseRestoreError is raised AND the temp file is still cleaned up
        with pytest.raises(DatabaseRestoreError, match="pg_restore"):
            await service.run(source=S3Source(key=None))
        assert not dump.exists()

    async def test_run_invokes_pg_restore_with_expected_args(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
    ) -> None:
        """Verify pg_restore is called with the configured host/port/user/db and the dump path."""
        # Given a local dump and mocks for subprocess / drop
        dump = tmp_path / "user.dump"
        dump.write_bytes(b"dump")
        mocker.patch("vapi.lib.db_restore.drop_and_recreate_database", new=AsyncMock())
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_exec = mocker.patch(
            "vapi.lib.db_restore.asyncio.create_subprocess_exec",
            return_value=mock_process,
        )

        service = DatabaseRestoreService()

        # When restoring
        await service.run(source=LocalFileSource(path=dump))

        # Then pg_restore was called with the expected positional args
        args, _kwargs = mock_exec.call_args
        assert args[0] == "pg_restore"
        assert "--no-owner" in args
        assert "--no-privileges" in args
        assert str(dump) in args


class TestRunIntegration:
    """End-to-end test: dump a real Postgres, then restore it."""

    @pytest.mark.serial
    async def test_restore_from_pg_dump_file_roundtrip(
        self,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """Verify DatabaseRestoreService can restore a pg_dump -Fc file produced from the live DB."""
        # Given a dump of the current test database
        from tortoise import Tortoise

        pg = settings.postgres
        dump_file = tmp_path / "roundtrip.dump"

        proc = await asyncio.create_subprocess_exec(
            "pg_dump",
            "-Fc",
            "-h",
            pg.host,
            "-p",
            str(pg.port),
            "-U",
            pg.user,
            "-d",
            pg.database,
            "-f",
            str(dump_file),
            env={**os.environ, "PGPASSWORD": pg.password},
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()
        assert proc.returncode == 0, stderr.decode()
        assert dump_file.stat().st_size > 0

        # Close Tortoise connections so drop_and_recreate_database can drop the DB
        await Tortoise.close_connections()

        # When restoring from the dump file
        try:
            service = DatabaseRestoreService()
            await service.run(source=LocalFileSource(path=dump_file))
        finally:
            # Reinitialize Tortoise so subsequent tests / fixtures see a working connection
            from vapi.lib.database import init_tortoise

            await init_tortoise()

        # Then a basic query against the restored DB succeeds
        conn = Tortoise.get_connection("default")
        _, rows = await conn.execute_query("SELECT 1 AS ok")
        assert rows[0]["ok"] == 1
