"""Tests for the scheduled tasks."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest

from vapi.db.sql_models.audit_log import AuditLog
from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.character import Character, CharacterTrait
from vapi.domain.services import AWSS3Service
from vapi.lib.scheduled_tasks import purge_db_expired_items
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


class TestPurgeDBExpiredItems:
    """Tests for the purge_db_expired_items task."""

    async def test_purge_db_expired_objects(
        self,
        character_factory: Callable[..., Any],
        mocker: MockerFixture,
    ) -> None:
        """Verify archived characters older than 30 days are purged by the cleanup task."""
        # Given: Mock DB init since connections are already open in tests
        mocker.patch("vapi.lib.database.init_tortoise", return_value=None)
        mocker.patch("tortoise.Tortoise.close_connections", return_value=None)

        old_date = time_now() - timedelta(days=60)

        character_old_not_archived = await character_factory(is_archived=False)
        character_old_archived = await character_factory(is_archived=True)
        character_new_not_archived = await character_factory(is_archived=False)
        character_new_archived = await character_factory(is_archived=True)

        # Bypass auto_now to set old date_modified directly via filter update
        await Character.filter(id=character_old_not_archived.id).update(date_modified=old_date)
        await Character.filter(id=character_old_archived.id).update(date_modified=old_date)

        # When we run the task
        await purge_db_expired_items({})

        # Then non-archived and recently-modified characters are not deleted
        for char in [
            character_old_not_archived,
            character_new_not_archived,
            character_new_archived,
        ]:
            assert await Character.filter(id=char.id).first() is not None

        # Then old archived characters are deleted
        assert await Character.filter(id=character_old_archived.id).first() is None

    async def test_purge_db_expired_audit_logs(
        self,
        developer_factory: Callable[..., Any],
        mocker: MockerFixture,
    ) -> None:
        """Verify audit log entries older than 30 days are purged by the cleanup task."""
        # Given: Mock DB init since connections are already open in tests
        mocker.patch("vapi.lib.database.init_tortoise", return_value=None)
        mocker.patch("tortoise.Tortoise.close_connections", return_value=None)

        old_date = time_now() - timedelta(days=60)

        developer = await developer_factory()
        audit_log_old = await AuditLog.create(
            developer=developer,
            handler="test_handler",
            handler_name="test_handler_name",
            name="test_name",
            method="GET",
            url="https://test.com",
        )
        audit_log_new = await AuditLog.create(
            developer=developer,
            handler="test_handler",
            handler_name="test_handler_name",
            name="test_name",
            method="GET",
            url="https://test.com",
        )

        # Bypass auto_now to set old date_modified directly
        await AuditLog.filter(id=audit_log_old.id).update(date_modified=old_date)

        # When we run the task
        await purge_db_expired_items({})

        # Then old audit logs are deleted
        assert await AuditLog.filter(id=audit_log_old.id).first() is None

        # Then recent audit logs are not deleted
        assert await AuditLog.filter(id=audit_log_new.id).first() is not None

        # Cleanup
        await AuditLog.filter(id=audit_log_new.id).delete()


class TestPurgeS3AssetsErrorIsolation:
    """Tests for per-asset error isolation in S3 cleanup."""

    async def test_s3_per_asset_error_does_not_block_others(
        self,
        s3asset_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        mocker: MockerFixture,
    ) -> None:
        """Verify a failure deleting one S3 asset does not prevent deletion of subsequent assets."""
        # Given: Mock DB init since connections are already open in tests
        mocker.patch("vapi.lib.database.init_tortoise", return_value=None)
        mocker.patch("tortoise.Tortoise.close_connections", return_value=None)

        old_date = time_now() - timedelta(days=60)

        # Create company and user explicitly so s3asset_factory has a valid company FK
        company = await company_factory()
        user = await user_factory(company=company)

        asset_1 = await s3asset_factory(is_archived=True, company=company, uploaded_by=user)
        asset_2 = await s3asset_factory(is_archived=True, company=company, uploaded_by=user)

        # Bypass auto_now to set old date_modified directly
        await S3Asset.filter(id=asset_1.id).update(date_modified=old_date)
        await S3Asset.filter(id=asset_2.id).update(date_modified=old_date)

        # Given delete_asset fails on the first asset but succeeds on the second
        call_count = 0

        asset_1_id = str(asset_1.id)

        async def mock_delete_asset(asset: S3Asset) -> None:
            nonlocal call_count
            call_count += 1
            # Compare as strings to avoid uuid vs uuid_utils type mismatch
            if str(asset.id) == asset_1_id:
                msg = "Simulated S3 failure"
                raise RuntimeError(msg)
            await asset.delete()

        mocker.patch.object(AWSS3Service, "delete_asset", side_effect=mock_delete_asset)

        # When we run the task
        await purge_db_expired_items({})

        # Then both assets were attempted (delete_asset called twice)
        assert call_count == 2

        # Then asset_1 still exists (delete failed) and asset_2 was deleted
        assert await S3Asset.filter(id=asset_1_id).first() is not None
        assert await S3Asset.filter(id=str(asset_2.id)).first() is None

        # Cleanup
        await S3Asset.filter(id=asset_1_id).delete()


class TestPurgeTemporaryCharacters:
    """Tests for the _purge_temporary_characters helper."""

    async def test_purge_old_temporary_characters(
        self,
        character_factory: Callable[..., Any],
        mocker: MockerFixture,
    ) -> None:
        """Verify temporary non-chargen characters modified more than 24 hours ago are deleted."""
        # Given: Mock DB init since connections are already open in tests
        mocker.patch("vapi.lib.database.init_tortoise", return_value=None)
        mocker.patch("tortoise.Tortoise.close_connections", return_value=None)

        # Given a temporary non-chargen character modified more than 24 hours ago
        old_temp = await character_factory(
            is_temporary=True,
            is_chargen=False,
        )
        old_date = time_now() - timedelta(hours=48)
        await Character.filter(id=old_temp.id).update(date_modified=old_date)

        # When we run the task
        await purge_db_expired_items({})

        # Then the old temporary character is deleted
        assert await Character.filter(id=old_temp.id).first() is None

    async def test_keep_recent_temporary_characters(
        self,
        character_factory: Callable[..., Any],
        mocker: MockerFixture,
    ) -> None:
        """Verify temporary characters modified within the last 24 hours are not deleted."""
        # Given
        mocker.patch("vapi.lib.database.init_tortoise", return_value=None)
        mocker.patch("tortoise.Tortoise.close_connections", return_value=None)

        # Given a temporary non-chargen character modified recently
        recent_temp = await character_factory(
            is_temporary=True,
            is_chargen=False,
        )

        # When we run the task
        await purge_db_expired_items({})

        # Then the recent temporary character is NOT deleted
        assert await Character.filter(id=recent_temp.id).first() is not None

    async def test_keep_chargen_temporary_characters(
        self,
        character_factory: Callable[..., Any],
        mocker: MockerFixture,
    ) -> None:
        """Verify temporary characters with is_chargen=True are not deleted."""
        # Given
        mocker.patch("vapi.lib.database.init_tortoise", return_value=None)
        mocker.patch("tortoise.Tortoise.close_connections", return_value=None)

        # Given a temporary chargen character modified more than 24 hours ago
        chargen_char = await character_factory(
            is_temporary=True,
            is_chargen=True,
        )
        old_date = time_now() - timedelta(hours=48)
        await Character.filter(id=chargen_char.id).update(date_modified=old_date)

        # When we run the task
        await purge_db_expired_items({})

        # Then the chargen character is NOT deleted (chargen session cleanup handles these)
        assert await Character.filter(id=chargen_char.id).first() is not None

    async def test_keep_non_temporary_characters(
        self,
        character_factory: Callable[..., Any],
        mocker: MockerFixture,
    ) -> None:
        """Verify non-temporary characters are never deleted by the temporary purge."""
        # Given
        mocker.patch("vapi.lib.database.init_tortoise", return_value=None)
        mocker.patch("tortoise.Tortoise.close_connections", return_value=None)

        # Given a regular character
        regular_char = await character_factory(
            is_temporary=False,
            is_chargen=False,
        )

        # When we run the task
        await purge_db_expired_items({})

        # Then the regular character is NOT deleted
        assert await Character.filter(id=regular_char.id).first() is not None

    async def test_purge_temporary_character_cleans_up_traits(
        self,
        character_factory: Callable[..., Any],
        character_trait_factory: Callable[..., Any],
        mocker: MockerFixture,
    ) -> None:
        """Verify CharacterTraits are cleaned up when a temporary character is purged."""
        # Given
        mocker.patch("vapi.lib.database.init_tortoise", return_value=None)
        mocker.patch("tortoise.Tortoise.close_connections", return_value=None)

        # Given a temporary character with a trait
        temp_char = await character_factory(
            is_temporary=True,
            is_chargen=False,
        )
        trait_record = await character_trait_factory(
            character=temp_char,
            value=3,
        )

        # Given the character is older than 24 hours
        old_date = time_now() - timedelta(hours=48)
        await Character.filter(id=temp_char.id).update(date_modified=old_date)

        # When we run the task
        await purge_db_expired_items({})

        # Then both the character and its trait are deleted
        assert await Character.filter(id=temp_char.id).first() is None
        assert await CharacterTrait.filter(id=trait_record.id).first() is None
