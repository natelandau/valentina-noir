"""Tests for the scheduled tasks."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from beanie import PydanticObjectId

from vapi.db.models import AuditLog, Character
from vapi.lib.scheduled_tasks import purge_db_expired_items
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

    from vapi.db.models import Company, User

pytestmark = pytest.mark.anyio


class TestPurgeDBExpiredItems:
    """Tests for the purge_db_expired_items task."""

    async def test_purge_db_expired_objects(
        self,
        company_factory: Callable[[dict[str, ...]], Company],
        user_factory: Callable[[dict[str, ...]], User],
        character_factory: Callable[[dict[str, ...]], Character],
        mocker: MockerFixture,
        debug: Callable[[...], None],
    ) -> None:
        """Test the database cleanup task."""
        # Given: Mock init_database since DB is already initialized by test fixtures
        mocker.patch("vapi.lib.database.init_database", return_value=None)

        # Given
        old_date = time_now() - timedelta(days=60)

        company = await company_factory()
        user = await user_factory(company_id=company.id)
        character_old_not_archived = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            is_archived=False,
        )
        character_old_archived = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            is_archived=True,
        )
        character_new_not_archived = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            is_archived=False,
        )
        character_new_archived = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            is_archived=True,
        )

        # Given: Bypass Beanie hooks to set old date_modified directly in MongoDB
        collection = Character.get_pymongo_collection()
        await collection.update_one(
            {"_id": character_old_not_archived.id},
            {"$set": {"date_modified": old_date}},
        )
        await collection.update_one(
            {"_id": character_old_archived.id},
            {"$set": {"date_modified": old_date}},
        )

        # When we run the task
        mock_ctx: dict[str, ...] = {}
        await purge_db_expired_items(mock_ctx)

        # Then objects newer than the cutoff date are not deleted
        for character in [
            character_old_not_archived,
            character_new_not_archived,
            character_new_archived,
        ]:
            db_object = await Character.get(character.id)
            assert db_object is not None

        # Then old objects that are archived are deleted
        for character in [character_old_archived]:
            db_object = await Character.get(character.id)
            assert db_object is None

    async def test_purge_db_expired_audit_logs(
        self,
        mocker: MockerFixture,
        debug: Callable[[...], None],
    ) -> None:
        """Test the database cleanup task."""
        # Given: Mock init_database since DB is already initialized by test fixtures
        mocker.patch("vapi.lib.database.init_database", return_value=None)

        # Given
        old_date = time_now() - timedelta(days=60)

        audit_log_old = await AuditLog(
            developer_id=PydanticObjectId(),
            handler="test_handler",
            handler_name="test_handler_name",
            name="test_name",
            summary="test_summary",
            operation_id="test_operation_id",
            method="GET",
            url="https://test.com",
            request_json={"test": "test"},
            request_body="test",
            path_params={"test": "test"},
            query_params={"test": "test"},
        ).insert()
        audit_log_new = await AuditLog(
            developer_id=PydanticObjectId(),
            handler="test_handler",
            handler_name="test_handler_name",
            name="test_name",
            summary="test_summary",
            operation_id="test_operation_id",
            method="GET",
            url="https://test.com",
            request_json={"test": "test"},
            request_body="test",
            path_params={"test": "test"},
            query_params={"test": "test"},
        ).insert()

        collection = AuditLog.get_pymongo_collection()
        await collection.update_one(
            {"_id": audit_log_old.id},
            {"$set": {"date_modified": old_date}},
        )

        # When we run the task
        mock_ctx: dict[str, ...] = {}
        await purge_db_expired_items(mock_ctx)

        # Then old audit logs are deleted
        db_object = await AuditLog.get(audit_log_old.id)
        assert db_object is None

        # Then new audit logs are not deleted
        db_object = await AuditLog.get(audit_log_new.id)
        assert db_object is not None
