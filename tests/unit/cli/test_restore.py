"""Tests for the `app restore` CLI command."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from click.testing import CliRunner

from vapi.cli.restore import restore
from vapi.lib.exceptions import DatabaseRestoreError

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


class TestRestoreCli:
    """Tests for the restore Click command."""

    def test_file_and_s3_path_are_mutually_exclusive(self, tmp_path: Path) -> None:
        """Verify passing both --file and --s3-path fails with a usage error."""
        # Given a dump file to pass via --file
        dump = tmp_path / "x.dump"
        dump.write_bytes(b"x")

        runner = CliRunner()

        # When invoking with both flags
        result = runner.invoke(
            restore,
            ["--file", str(dump), "--s3-path", "db_backups/2026-04-15.dump", "--yes"],
        )

        # Then exit code is 2 (usage error) and message mentions both flags
        assert result.exit_code == 2
        assert "--file" in result.output
        assert "--s3-path" in result.output

    def test_confirmation_no_aborts_without_calling_service(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Verify answering 'n' to the prompt aborts without touching the DB."""
        # Given a mocked service that should never be called
        mock_service = mocker.patch("vapi.cli.restore.DatabaseRestoreService")

        runner = CliRunner()

        # When invoking and answering 'n' at the prompt
        result = runner.invoke(restore, [], input="n\n")

        # Then the service was never constructed and exit code is 0
        assert result.exit_code == 0
        mock_service.assert_not_called()

    def test_yes_flag_skips_prompt_and_runs_service(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Verify --yes skips the prompt and invokes the service."""
        # Given a mocked service.run
        mock_service_instance = mocker.MagicMock()
        mock_service_instance.run = AsyncMock()
        mocker.patch(
            "vapi.cli.restore.DatabaseRestoreService",
            return_value=mock_service_instance,
        )

        runner = CliRunner()

        # When invoking with --yes
        result = runner.invoke(restore, ["--yes"])

        # Then the service was called with an S3Source(key=None) and exit is 0
        assert result.exit_code == 0, result.output
        mock_service_instance.run.assert_awaited_once()
        source = mock_service_instance.run.await_args.kwargs["source"]
        from vapi.lib.db_restore import S3Source

        assert isinstance(source, S3Source)
        assert source.key is None

    def test_service_error_produces_non_zero_exit(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Verify a DatabaseRestoreError from the service produces a non-zero exit."""
        # Given a service that raises
        mock_service_instance = mocker.MagicMock()
        mock_service_instance.run = AsyncMock(side_effect=DatabaseRestoreError("boom"))
        mocker.patch(
            "vapi.cli.restore.DatabaseRestoreService",
            return_value=mock_service_instance,
        )

        runner = CliRunner()

        # When invoking with --yes and the service fails
        result = runner.invoke(restore, ["--yes"])

        # Then exit code is non-zero and the message is surfaced
        assert result.exit_code != 0
        assert "boom" in result.output

    def test_file_flag_builds_local_file_source(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
    ) -> None:
        """Verify --file passes a LocalFileSource to the service."""
        # Given a dump file and a mocked service
        dump = tmp_path / "x.dump"
        dump.write_bytes(b"x")
        mock_service_instance = mocker.MagicMock()
        mock_service_instance.run = AsyncMock()
        mocker.patch(
            "vapi.cli.restore.DatabaseRestoreService",
            return_value=mock_service_instance,
        )

        runner = CliRunner()

        # When invoking with --file and --yes
        result = runner.invoke(restore, ["--file", str(dump), "--yes"])

        # Then the service was called with a LocalFileSource wrapping that path
        assert result.exit_code == 0, result.output
        from vapi.lib.db_restore import LocalFileSource

        source = mock_service_instance.run.await_args.kwargs["source"]
        assert isinstance(source, LocalFileSource)
        assert source.path == dump
