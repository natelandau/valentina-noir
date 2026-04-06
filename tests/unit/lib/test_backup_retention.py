"""Tests for the backup retention logic."""

from __future__ import annotations

from datetime import date, timedelta

from vapi.config.base import BackupSettings
from vapi.lib.scheduled_tasks import _compute_backups_to_delete

_PREFIX = "db_backups"


def _key(d: date) -> str:
    return f"{_PREFIX}/{d.isoformat()}.dump"


def _keys(dates: list[date]) -> list[str]:
    return [_key(d) for d in dates]


class TestComputeBackupsToDelete:
    """Tests for the _compute_backups_to_delete function."""

    def test_empty_input_returns_empty(self) -> None:
        """Verify empty input returns no deletions."""
        # Given no backups
        settings = BackupSettings()

        # When computing deletions
        result = _compute_backups_to_delete([], settings)

        # Then nothing to delete
        assert result == []

    def test_fewer_backups_than_daily_retention(self) -> None:
        """Verify no deletions when backup count is within daily retention."""
        # Given 3 backups with 7-day retention
        settings = BackupSettings(retain_daily=7)
        keys = _keys([date(2026, 4, 4), date(2026, 4, 5), date(2026, 4, 6)])

        # When computing deletions
        result = _compute_backups_to_delete(keys, settings)

        # Then nothing to delete
        assert result == []

    def test_daily_retention_prunes_oldest(self) -> None:
        """Verify daily retention keeps only the most recent N backups."""
        # Given 10 consecutive daily backups with retain_daily=3
        settings = BackupSettings(
            retain_daily=3, retain_weekly=0, retain_monthly=0, retain_yearly=0
        )
        dates = [date(2026, 3, 28) + timedelta(days=i) for i in range(10)]  # Mar 28 - Apr 6
        keys = _keys(dates)

        # When computing deletions
        result = _compute_backups_to_delete(keys, settings)

        # Then only the 3 most recent are kept
        kept = [k for k in keys if k not in result]
        assert len(kept) == 3
        assert _key(date(2026, 4, 6)) in kept
        assert _key(date(2026, 4, 5)) in kept
        assert _key(date(2026, 4, 4)) in kept

    def test_weekly_retention_keeps_oldest_per_week(self) -> None:
        """Verify weekly retention keeps the oldest backup from each ISO week."""
        # Given 21 daily backups (3 weeks) with retain_weekly=2, retain_daily=0
        settings = BackupSettings(
            retain_daily=0, retain_weekly=2, retain_monthly=0, retain_yearly=0
        )
        dates = [date(2026, 3, 16) + timedelta(days=i) for i in range(21)]  # Mar 16 - Apr 5
        keys = _keys(dates)

        # When computing deletions
        result = _compute_backups_to_delete(keys, settings)

        # Then oldest from the 2 most recent weeks are kept
        kept = [k for k in keys if k not in result]
        assert len(kept) == 2

    def test_monthly_retention_keeps_oldest_per_month(self) -> None:
        """Verify monthly retention keeps the oldest backup from each month."""
        # Given backups across 4 months with retain_monthly=3, no daily/weekly
        settings = BackupSettings(
            retain_daily=0, retain_weekly=0, retain_monthly=3, retain_yearly=0
        )
        dates = [
            date(2026, 1, 15),
            date(2026, 1, 20),
            date(2026, 2, 10),
            date(2026, 2, 25),
            date(2026, 3, 5),
            date(2026, 3, 30),
            date(2026, 4, 1),
            date(2026, 4, 6),
        ]
        keys = _keys(dates)

        # When computing deletions
        result = _compute_backups_to_delete(keys, settings)

        # Then oldest from the 3 most recent months are kept
        kept = [k for k in keys if k not in result]
        assert _key(date(2026, 2, 10)) in kept
        assert _key(date(2026, 3, 5)) in kept
        assert _key(date(2026, 4, 1)) in kept

    def test_yearly_retention_keeps_oldest_per_year(self) -> None:
        """Verify yearly retention keeps the oldest backup from each year."""
        # Given backups across 3 years with retain_yearly=2, no daily/weekly/monthly
        settings = BackupSettings(
            retain_daily=0, retain_weekly=0, retain_monthly=0, retain_yearly=2
        )
        dates = [
            date(2024, 6, 15),
            date(2024, 12, 20),
            date(2025, 3, 10),
            date(2025, 9, 25),
            date(2026, 1, 5),
            date(2026, 4, 6),
        ]
        keys = _keys(dates)

        # When computing deletions
        result = _compute_backups_to_delete(keys, settings)

        # Then oldest from the 2 most recent years are kept
        kept = [k for k in keys if k not in result]
        assert _key(date(2025, 3, 10)) in kept
        assert _key(date(2026, 1, 5)) in kept

    def test_overlapping_retention_deduplicates(self) -> None:
        """Verify a backup kept by multiple retention tiers is not duplicated."""
        # Given 7 daily backups with daily=7 and weekly=1
        settings = BackupSettings(
            retain_daily=7, retain_weekly=1, retain_monthly=0, retain_yearly=0
        )
        dates = [date(2026, 3, 31) + timedelta(days=i) for i in range(7)]  # Mar 31 - Apr 6
        keys = _keys(dates)

        # When computing deletions
        result = _compute_backups_to_delete(keys, settings)

        # Then nothing is deleted (all 7 kept by daily, weekly is a subset)
        assert result == []

    def test_gaps_in_backup_dates(self) -> None:
        """Verify retention handles non-consecutive backup dates correctly."""
        # Given backups with gaps
        settings = BackupSettings(
            retain_daily=2, retain_weekly=0, retain_monthly=0, retain_yearly=0
        )
        dates = [date(2026, 3, 1), date(2026, 3, 15), date(2026, 4, 1), date(2026, 4, 6)]
        keys = _keys(dates)

        # When computing deletions
        result = _compute_backups_to_delete(keys, settings)

        # Then only the 2 most recent are kept
        kept = [k for k in keys if k not in result]
        assert len(kept) == 2
        assert _key(date(2026, 4, 6)) in kept
        assert _key(date(2026, 4, 1)) in kept

    def test_single_backup(self) -> None:
        """Verify a single backup is never deleted regardless of retention."""
        # Given a single backup with retain_daily=0
        settings = BackupSettings(
            retain_daily=0, retain_weekly=0, retain_monthly=1, retain_yearly=0
        )
        keys = _keys([date(2026, 4, 6)])

        # When computing deletions
        result = _compute_backups_to_delete(keys, settings)

        # Then the single backup is kept by monthly retention
        assert result == []

    def test_all_retention_zero_deletes_everything(self) -> None:
        """Verify all backups are deleted when all retention values are zero."""
        # Given backups with all retention set to 0
        settings = BackupSettings(
            retain_daily=0, retain_weekly=0, retain_monthly=0, retain_yearly=0
        )
        keys = _keys([date(2026, 4, 5), date(2026, 4, 6)])

        # When computing deletions
        result = _compute_backups_to_delete(keys, settings)

        # Then all backups are deleted
        assert len(result) == 2

    def test_ignores_non_matching_keys(self) -> None:
        """Verify keys that don't match the expected pattern are left alone."""
        # Given a mix of valid and invalid keys
        settings = BackupSettings(retain_daily=1)
        keys = [
            "db_backups/2026-04-06.dump",
            "db_backups/not-a-date.dump",
            "db_backups/readme.txt",
        ]

        # When computing deletions
        result = _compute_backups_to_delete(keys, settings)

        # Then only valid parseable keys are candidates; invalid ones are not touched
        assert "db_backups/not-a-date.dump" not in result
        assert "db_backups/readme.txt" not in result
